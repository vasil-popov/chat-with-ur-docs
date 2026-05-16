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
      <SafeAreaView style={styles.container} edges={['bottom', 'left', 'right']}>

        <View style={styles.filterRow}>
          <TextInput style={styles.dateInput} value={startDate} onChangeText={setStartDate} onEndEditing={fetchWorkouts} placeholder="YYYY-MM-DD" placeholderTextColor={c.placeholder} />
          <Text style={styles.arrow}>→</Text>
          <TextInput style={styles.dateInput} value={endDate} onChangeText={setEndDate} onEndEditing={fetchWorkouts} placeholder="YYYY-MM-DD" placeholderTextColor={c.placeholder} />
          <TouchableOpacity style={styles.refreshBtn} onPress={fetchWorkouts}>
            <Text style={styles.refreshIcon}>↻</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.summaryBar}>
          <Text style={styles.summaryText}>
            {workouts.length} session{workouts.length !== 1 ? 's' : ''} · {totalExercises} exercise{totalExercises !== 1 ? 's' : ''}
          </Text>
        </View>

        {loading ? (
          <ActivityIndicator style={{ flex: 1 }} color={c.accent} />
        ) : (
          <ScrollView style={{ flex: 1 }} keyboardShouldPersistTaps="handled">
            {workouts.length === 0 && <Text style={styles.empty}>No workouts in this period</Text>}
            {workouts.map((ws) => (
              <View key={ws.session_id} style={styles.card}>
                <TouchableOpacity style={styles.cardHeader} onPress={() => toggle(ws.session_id)}>
                  <View>
                    <Text style={styles.sessionName}>{ws.session_name}</Text>
                    <Text style={styles.sessionMeta}>
                      {ws.date} · {ws.exercises.length} exercise{ws.exercises.length !== 1 ? 's' : ''}
                    </Text>
                  </View>
                  <Text style={styles.chevron}>{expanded.has(ws.session_id) ? '▲' : '▼'}</Text>
                </TouchableOpacity>

                {expanded.has(ws.session_id) && ws.exercises.map((ex) => (
                  <View key={ex.exercise_id} style={styles.exRow}>
                    <View style={styles.exInfo}>
                      <Text style={styles.exName}>{ex.name}</Text>
                      <Text style={styles.exDetails}>{formatDetails(ex)}</Text>
                    </View>
                    <TouchableOpacity onPress={() => handleDelete(ex.exercise_id, ex.name)} style={styles.iconBtn}>
                      <Text style={styles.icon}>🗑️</Text>
                    </TouchableOpacity>
                  </View>
                ))}
              </View>
            ))}
            <View style={{ height: 90 }} />
          </ScrollView>
        )}

        {showForm && (
          <View style={styles.form}>
            <Text style={styles.formTitle}>Log Exercise</Text>
            <View style={styles.row2}>
              <TextInput style={[styles.input, { flex: 1 }]} placeholder="Exercise name" value={form.exercise_name} onChangeText={(v) => setForm((f) => ({ ...f, exercise_name: v }))} placeholderTextColor={c.placeholder} />
              <View style={{ width: 8 }} />
              <TextInput style={[styles.input, { flex: 1 }]} placeholder="Category" value={form.category} onChangeText={(v) => setForm((f) => ({ ...f, category: v }))} placeholderTextColor={c.placeholder} />
            </View>
            <View style={styles.row2}>
              <TextInput style={[styles.input, { flex: 1 }]} placeholder="Session name" value={form.session_name} onChangeText={(v) => setForm((f) => ({ ...f, session_name: v }))} placeholderTextColor={c.placeholder} />
              <View style={{ width: 8 }} />
              <TextInput style={[styles.input, { flex: 1 }]} placeholder="Date (YYYY-MM-DD)" value={form.workout_date} onChangeText={(v) => setForm((f) => ({ ...f, workout_date: v }))} placeholderTextColor={c.placeholder} />
            </View>
            <View style={styles.row2}>
              <TextInput style={[styles.input, { flex: 1 }]} placeholder="Sets" keyboardType="number-pad" value={form.sets} onChangeText={(v) => setForm((f) => ({ ...f, sets: v }))} placeholderTextColor={c.placeholder} />
              <View style={{ width: 8 }} />
              <TextInput style={[styles.input, { flex: 1 }]} placeholder="Reps" keyboardType="number-pad" value={form.reps} onChangeText={(v) => setForm((f) => ({ ...f, reps: v }))} placeholderTextColor={c.placeholder} />
              <View style={{ width: 8 }} />
              <TextInput style={[styles.input, { flex: 1 }]} placeholder="kg" keyboardType="decimal-pad" value={form.weight_kg} onChangeText={(v) => setForm((f) => ({ ...f, weight_kg: v }))} placeholderTextColor={c.placeholder} />
            </View>
            <View style={styles.row2}>
              <TextInput style={[styles.input, { flex: 1 }]} placeholder="Duration (min)" keyboardType="number-pad" value={form.duration_minutes} onChangeText={(v) => setForm((f) => ({ ...f, duration_minutes: v }))} placeholderTextColor={c.placeholder} />
              <View style={{ width: 8 }} />
              <TextInput style={[styles.input, { flex: 1 }]} placeholder="Distance (km)" keyboardType="decimal-pad" value={form.distance_km} onChangeText={(v) => setForm((f) => ({ ...f, distance_km: v }))} placeholderTextColor={c.placeholder} />
            </View>
            <View style={styles.formActions}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => { setShowForm(false); setForm(emptyForm()); }}>
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.saveBtn} onPress={handleSave}>
                <Text style={styles.saveBtnText}>Log Exercise</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {!showForm && (
          <TouchableOpacity style={styles.fab} onPress={() => setShowForm(true)}>
            <Text style={styles.fabText}>+</Text>
          </TouchableOpacity>
        )}
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

function makeStyles(c: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: c.background },
    filterRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, backgroundColor: c.surface, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: c.border },
    dateInput: { flex: 1, backgroundColor: c.inputBg, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7, fontSize: 13, color: c.text },
    arrow: { marginHorizontal: 6, color: c.textMuted, fontSize: 14 },
    refreshBtn: { marginLeft: 8, width: 32, height: 32, borderRadius: 16, backgroundColor: c.accent, justifyContent: 'center', alignItems: 'center' },
    refreshIcon: { color: '#fff', fontSize: 16 },
    summaryBar: { paddingHorizontal: 16, paddingVertical: 10, backgroundColor: c.surface, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: c.border },
    summaryText: { fontSize: 13, color: c.textMuted },
    card: { backgroundColor: c.surface, marginTop: 10, marginHorizontal: 12, borderRadius: 12, overflow: 'hidden', elevation: 1, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.12, shadowRadius: 2 },
    cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 12, backgroundColor: c.surfaceVariant, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: c.border },
    sessionName: { fontSize: 15, fontWeight: '700', color: c.text },
    sessionMeta: { fontSize: 12, color: c.textMuted, marginTop: 2 },
    chevron: { fontSize: 11, color: c.textMuted },
    exRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: c.borderLight },
    exInfo: { flex: 1 },
    exName: { fontSize: 14, fontWeight: '600', color: c.text },
    exDetails: { fontSize: 12, color: c.textMuted, marginTop: 2 },
    iconBtn: { padding: 6 },
    icon: { fontSize: 16 },
    empty: { textAlign: 'center', marginTop: 60, color: c.textMuted, fontSize: 15 },
    form: { backgroundColor: c.surface, padding: 14, borderTopWidth: StyleSheet.hairlineWidth, borderColor: c.border },
    formTitle: { fontSize: 16, fontWeight: '600', marginBottom: 10, color: c.text },
    row2: { flexDirection: 'row', marginBottom: 0 },
    input: { backgroundColor: c.inputBg, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 9, fontSize: 14, marginBottom: 8, color: c.text },
    formActions: { flexDirection: 'row', gap: 10, marginTop: 4 },
    cancelBtn: { flex: 1, paddingVertical: 13, borderRadius: 10, backgroundColor: c.cancelBg, alignItems: 'center' },
    cancelBtnText: { fontSize: 15, color: c.cancelText },
    saveBtn: { flex: 2, paddingVertical: 13, borderRadius: 10, backgroundColor: c.accent, alignItems: 'center' },
    saveBtnText: { fontSize: 15, color: '#fff', fontWeight: '600' },
    fab: { position: 'absolute', bottom: 28, right: 24, width: 56, height: 56, borderRadius: 28, backgroundColor: c.accent, justifyContent: 'center', alignItems: 'center', elevation: 5, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.3, shadowRadius: 4 },
    fabText: { color: '#fff', fontSize: 30, lineHeight: 34 },
  });
}
