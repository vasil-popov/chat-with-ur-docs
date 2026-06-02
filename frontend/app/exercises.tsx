import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useTheme, type ThemeColors } from '../src/theme';
import { type ExerciseEntry, type WorkoutSession, createExercise, deleteExercise, getWorkouts } from '../src/api';

const today = new Date();
const todayStr = today.toISOString().split('T')[0];
const firstOfMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`;

type FormState = {
  exercise_name: string; category: string; session_name: string; workout_date: string;
  duration_minutes: string; sets: string; reps: string; weight_kg: string; distance_km: string;
};

const emptyForm = (): FormState => ({
  exercise_name: '', category: '', session_name: 'Daily Workout', workout_date: todayStr,
  duration_minutes: '', sets: '', reps: '', weight_kg: '', distance_km: '',
});

function formatDetails(ex: ExerciseEntry): string {
  const parts: string[] = [ex.category];
  if (ex.sets && ex.reps) parts.push(`${ex.sets}×${ex.reps}`);
  if (ex.weight_kg) parts.push(`${ex.weight_kg} kg`);
  if (ex.duration) parts.push(`${ex.duration} min`);
  if (ex.distance_km) parts.push(`${ex.distance_km} km`);
  return parts.join(' · ');
}

export default function ExercisesScreen() {
  const { theme } = useTheme();
  const c = theme.colors;
  const styles = useMemo(() => makeStyles(c), [theme]);

  const [workouts, setWorkouts] = useState<WorkoutSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [startDate, setStartDate] = useState(firstOfMonth);
  const [endDate, setEndDate] = useState(todayStr);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm());

  useEffect(() => { fetchWorkouts(); }, [startDate, endDate]);

  const fetchWorkouts = async () => {
    setLoading(true);
    try {
      const data = await getWorkouts(startDate, endDate);
      setWorkouts(data);
      setExpanded(new Set(data.map((ws) => ws.session_id)));
    } catch {
      Alert.alert('Error', 'Could not load workouts. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  const toggle = (id: string) => setExpanded((prev) => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const handleDelete = (id: string, name: string) => {
    Alert.alert('Delete exercise', `Delete "${name}"?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await deleteExercise(id); fetchWorkouts(); }
        catch { Alert.alert('Error', 'Failed to delete exercise.'); }
      }},
    ]);
  };

  const handleSave = async () => {
    if (!form.exercise_name || !form.category || !form.workout_date) {
      Alert.alert('Validation', 'Exercise name, category and date are required.'); return;
    }
    try {
      await createExercise({
        exercise_name: form.exercise_name.trim(),
        category: form.category.trim(),
        workout_date: form.workout_date,
        session_name: form.session_name.trim() || 'Daily Workout',
        duration_minutes: form.duration_minutes ? parseInt(form.duration_minutes) : undefined,
        sets: form.sets ? parseInt(form.sets) : undefined,
        reps: form.reps ? parseInt(form.reps) : undefined,
        weight_kg: form.weight_kg ? parseFloat(form.weight_kg) : undefined,
        distance_km: form.distance_km ? parseFloat(form.distance_km) : undefined,
      });
      setShowForm(false);
      setForm(emptyForm());
      fetchWorkouts();
    } catch {
      Alert.alert('Error', 'Failed to save exercise.');
    }
  };

  const totalExercises = workouts.reduce((sum, ws) => sum + ws.exercises.length, 0);

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <SafeAreaView style={[styles.container, { backgroundColor: c.background }]} edges={['bottom', 'left', 'right']}>

        {/* Date filter */}
        <View style={[styles.filterRow, { backgroundColor: c.surface, borderBottomColor: c.border }]}>
          <Ionicons name="calendar-outline" size={16} color={c.textMuted} style={{ marginRight: 8 }} />
          <TextInput
            style={[styles.dateInput, { backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]}
            value={startDate}
            onChangeText={setStartDate}
            onEndEditing={fetchWorkouts}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={c.placeholder}
          />
          <Text style={[styles.arrow, { color: c.textMuted }]}>→</Text>
          <TextInput
            style={[styles.dateInput, { backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]}
            value={endDate}
            onChangeText={setEndDate}
            onEndEditing={fetchWorkouts}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={c.placeholder}
          />
          <TouchableOpacity style={[styles.refreshBtn, { backgroundColor: c.accent }]} onPress={fetchWorkouts}>
            <Ionicons name="refresh" size={16} color="#ffffff" />
          </TouchableOpacity>
        </View>

        {/* Summary bar */}
        <View style={[styles.summaryBar, { backgroundColor: c.surface, borderBottomColor: c.border }]}>
          <Text style={[styles.summaryText, { color: c.textMuted }]}>
            {workouts.length} session{workouts.length !== 1 ? 's' : ''} · {totalExercises} exercise{totalExercises !== 1 ? 's' : ''}
          </Text>
        </View>

        {loading ? (
          <ActivityIndicator style={{ flex: 1 }} color={c.accent} />
        ) : (
          <ScrollView style={{ flex: 1 }} keyboardShouldPersistTaps="handled">
            {workouts.length === 0 && (
              <View style={styles.emptyWrap}>
                <Ionicons name="barbell-outline" size={40} color={c.textFaint} />
                <Text style={[styles.empty, { color: c.textMuted }]}>No workouts in this period</Text>
              </View>
            )}
            {workouts.map((ws) => (
              <View key={ws.session_id} style={[styles.card, { backgroundColor: c.surface, borderColor: c.border }]}>
                <TouchableOpacity
                  style={[styles.cardHeader, { backgroundColor: c.surfaceVariant, borderBottomColor: c.border }]}
                  onPress={() => toggle(ws.session_id)}
                >
                  <View style={[styles.sessionAccent, { backgroundColor: c.accent }]} />
                  <View style={styles.sessionInfo}>
                    <Text style={[styles.sessionName, { color: c.text }]}>{ws.session_name}</Text>
                    <Text style={[styles.sessionMeta, { color: c.textMuted }]}>{ws.date}</Text>
                  </View>
                  <View style={[styles.countBadge, { backgroundColor: c.drawerActiveBg }]}>
                    <Text style={[styles.countBadgeText, { color: c.accent }]}>{ws.exercises.length}</Text>
                  </View>
                  <Ionicons
                    name={expanded.has(ws.session_id) ? 'chevron-up' : 'chevron-down'}
                    size={16}
                    color={c.textMuted}
                    style={{ marginLeft: 8 }}
                  />
                </TouchableOpacity>

                {expanded.has(ws.session_id) && ws.exercises.map((ex) => (
                  <View key={ex.exercise_id} style={[styles.exRow, { borderBottomColor: c.borderLight }]}>
                    <View style={styles.exInfo}>
                      <Text style={[styles.exName, { color: c.text }]}>{ex.name}</Text>
                      <View style={styles.exMeta}>
                        <View style={[styles.catPill, { backgroundColor: c.drawerActiveBg }]}>
                          <Text style={[styles.catPillText, { color: c.accent }]}>{ex.category}</Text>
                        </View>
                        <Text style={[styles.exDetails, { color: c.textMuted }]}>{formatDetails(ex).replace(ex.category + ' · ', '')}</Text>
                      </View>
                    </View>
                    <TouchableOpacity onPress={() => handleDelete(ex.exercise_id, ex.name)} style={styles.iconBtn} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                      <Ionicons name="trash-outline" size={16} color={c.danger} />
                    </TouchableOpacity>
                  </View>
                ))}
              </View>
            ))}
            <View style={{ height: 90 }} />
          </ScrollView>
        )}

        {/* Form */}
        {showForm && (
          <View style={[styles.form, { backgroundColor: c.surface, borderTopColor: c.border }]}>
            <Text style={[styles.formTitle, { color: c.text }]}>Log Exercise</Text>
            <View style={styles.row2}>
              <TextInput style={[styles.input, { flex: 1, backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]} placeholder="Exercise name" value={form.exercise_name} onChangeText={(v) => setForm((f) => ({ ...f, exercise_name: v }))} placeholderTextColor={c.placeholder} />
              <View style={{ width: 8 }} />
              <TextInput style={[styles.input, { flex: 1, backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]} placeholder="Category" value={form.category} onChangeText={(v) => setForm((f) => ({ ...f, category: v }))} placeholderTextColor={c.placeholder} />
            </View>
            <View style={styles.row2}>
              <TextInput style={[styles.input, { flex: 1, backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]} placeholder="Session name" value={form.session_name} onChangeText={(v) => setForm((f) => ({ ...f, session_name: v }))} placeholderTextColor={c.placeholder} />
              <View style={{ width: 8 }} />
              <TextInput style={[styles.input, { flex: 1, backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]} placeholder="Date (YYYY-MM-DD)" value={form.workout_date} onChangeText={(v) => setForm((f) => ({ ...f, workout_date: v }))} placeholderTextColor={c.placeholder} />
            </View>
            <View style={styles.row2}>
              <TextInput style={[styles.input, { flex: 1, backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]} placeholder="Sets" keyboardType="number-pad" value={form.sets} onChangeText={(v) => setForm((f) => ({ ...f, sets: v }))} placeholderTextColor={c.placeholder} />
              <View style={{ width: 8 }} />
              <TextInput style={[styles.input, { flex: 1, backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]} placeholder="Reps" keyboardType="number-pad" value={form.reps} onChangeText={(v) => setForm((f) => ({ ...f, reps: v }))} placeholderTextColor={c.placeholder} />
              <View style={{ width: 8 }} />
              <TextInput style={[styles.input, { flex: 1, backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]} placeholder="kg" keyboardType="decimal-pad" value={form.weight_kg} onChangeText={(v) => setForm((f) => ({ ...f, weight_kg: v }))} placeholderTextColor={c.placeholder} />
            </View>
            <View style={styles.row2}>
              <TextInput style={[styles.input, { flex: 1, backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]} placeholder="Duration (min)" keyboardType="number-pad" value={form.duration_minutes} onChangeText={(v) => setForm((f) => ({ ...f, duration_minutes: v }))} placeholderTextColor={c.placeholder} />
              <View style={{ width: 8 }} />
              <TextInput style={[styles.input, { flex: 1, backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]} placeholder="Distance (km)" keyboardType="decimal-pad" value={form.distance_km} onChangeText={(v) => setForm((f) => ({ ...f, distance_km: v }))} placeholderTextColor={c.placeholder} />
            </View>
            <View style={styles.formActions}>
              <TouchableOpacity style={[styles.cancelBtn, { backgroundColor: c.cancelBg }]} onPress={() => { setShowForm(false); setForm(emptyForm()); }}>
                <Text style={[styles.cancelBtnText, { color: c.cancelText }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.saveBtn, { backgroundColor: c.accent }]} onPress={handleSave}>
                <Text style={styles.saveBtnText}>Log Exercise</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {!showForm && (
          <TouchableOpacity style={[styles.fab, { backgroundColor: c.accent, shadowColor: c.accent }]} onPress={() => setShowForm(true)}>
            <Ionicons name="add" size={28} color="#ffffff" />
          </TouchableOpacity>
        )}
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

function makeStyles(c: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1 },
    filterRow: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: 12,
      paddingVertical: 10,
      borderBottomWidth: StyleSheet.hairlineWidth,
    },
    dateInput: {
      flex: 1,
      borderRadius: 10,
      paddingHorizontal: 10,
      paddingVertical: 8,
      fontSize: 13,
      borderWidth: 1,
    },
    arrow: { marginHorizontal: 8, fontSize: 14 },
    refreshBtn: {
      marginLeft: 10,
      width: 34,
      height: 34,
      borderRadius: 10,
      justifyContent: 'center',
      alignItems: 'center',
    },
    summaryBar: {
      paddingHorizontal: 16,
      paddingVertical: 10,
      borderBottomWidth: StyleSheet.hairlineWidth,
    },
    summaryText: { fontSize: 13 },

    card: {
      marginHorizontal: 12,
      marginTop: 10,
      borderRadius: 14,
      borderWidth: 1,
      overflow: 'hidden',
      elevation: 2,
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.1,
      shadowRadius: 3,
    },
    cardHeader: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: 14,
      paddingVertical: 12,
      borderBottomWidth: StyleSheet.hairlineWidth,
    },
    sessionAccent: {
      width: 4,
      height: 32,
      borderRadius: 2,
      marginRight: 12,
    },
    sessionInfo: { flex: 1 },
    sessionName: { fontSize: 15, fontWeight: '700' },
    sessionMeta: { fontSize: 12, marginTop: 2 },
    countBadge: {
      paddingHorizontal: 10,
      paddingVertical: 4,
      borderRadius: 20,
    },
    countBadgeText: { fontSize: 12, fontWeight: '700' },

    exRow: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: 14,
      paddingVertical: 12,
      borderBottomWidth: StyleSheet.hairlineWidth,
    },
    exInfo: { flex: 1 },
    exName: { fontSize: 14, fontWeight: '600' },
    exMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' },
    catPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 20 },
    catPillText: { fontSize: 11, fontWeight: '600' },
    exDetails: { fontSize: 12 },
    iconBtn: { padding: 4 },

    emptyWrap: { alignItems: 'center', marginTop: 80, gap: 12 },
    empty: { fontSize: 15 },

    form: {
      padding: 14,
      borderTopWidth: StyleSheet.hairlineWidth,
    },
    formTitle: { fontSize: 17, fontWeight: '700', marginBottom: 12 },
    row2: { flexDirection: 'row', marginBottom: 0 },
    input: {
      borderRadius: 12,
      paddingHorizontal: 12,
      paddingVertical: 10,
      fontSize: 14,
      marginBottom: 8,
      borderWidth: 1,
    },
    formActions: { flexDirection: 'row', gap: 10, marginTop: 4 },
    cancelBtn: { flex: 1, paddingVertical: 13, borderRadius: 12, alignItems: 'center' },
    cancelBtnText: { fontSize: 15, fontWeight: '600' },
    saveBtn: { flex: 2, paddingVertical: 13, borderRadius: 12, alignItems: 'center' },
    saveBtnText: { fontSize: 15, color: '#fff', fontWeight: '700' },

    fab: {
      position: 'absolute',
      bottom: 28,
      right: 24,
      width: 56,
      height: 56,
      borderRadius: 16,
      justifyContent: 'center',
      alignItems: 'center',
      elevation: 8,
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.4,
      shadowRadius: 8,
    },
  });
}
