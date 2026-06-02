import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useTheme, type ThemeColors } from '../src/theme';
import { type Expense, createExpense, deleteExpense, getExpenses, updateExpense } from '../src/api';

const today = new Date();
const todayStr = today.toISOString().split('T')[0];
const firstOfMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`;

const CATEGORY_COLORS = ['#7c6ef5', '#f59e0b', '#10b981', '#ef4444', '#3b82f6', '#ec4899', '#8b5cf6', '#f97316'];

function categoryColor(cat: string): string {
  let hash = 0;
  for (let i = 0; i < cat.length; i++) hash = cat.charCodeAt(i) + ((hash << 5) - hash);
  return CATEGORY_COLORS[Math.abs(hash) % CATEGORY_COLORS.length];
}

type FormState = {
  amount: string;
  category: string;
  description: string;
  transaction_date: string;
};

const emptyForm = (): FormState => ({
  amount: '',
  category: '',
  description: '',
  transaction_date: todayStr,
});

export default function ExpensesScreen() {
  const { theme } = useTheme();
  const c = theme.colors;
  const styles = useMemo(() => makeStyles(c), [theme]);

  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [loading, setLoading] = useState(false);
  const [startDate, setStartDate] = useState(firstOfMonth);
  const [endDate, setEndDate] = useState(todayStr);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());

  useEffect(() => { fetchExpenses(); }, [startDate, endDate]);

  const fetchExpenses = async () => {
    setLoading(true);
    try {
      setExpenses(await getExpenses(startDate, endDate));
    } catch {
      Alert.alert('Error', 'Could not load expenses. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  const openAdd = () => { setForm(emptyForm()); setEditingId(null); setShowForm(true); };

  const openEdit = (e: Expense) => {
    setForm({ amount: String(e.amount), category: e.category, description: e.description ?? '', transaction_date: e.date });
    setEditingId(e.id);
    setShowForm(true);
  };

  const closeForm = () => { setShowForm(false); setEditingId(null); };

  const handleSave = async () => {
    if (!form.amount || !form.category || !form.transaction_date) {
      Alert.alert('Validation', 'Amount, category and date are required.'); return;
    }
    const parsed = parseFloat(form.amount);
    if (isNaN(parsed) || parsed <= 0) {
      Alert.alert('Validation', 'Amount must be a positive number.'); return;
    }
    try {
      const payload = { amount: parsed, category: form.category.trim(), description: form.description.trim() || undefined, transaction_date: form.transaction_date };
      if (editingId) await updateExpense(editingId, payload);
      else await createExpense(payload);
      closeForm();
      fetchExpenses();
    } catch {
      Alert.alert('Error', 'Failed to save expense.');
    }
  };

  const handleDelete = (id: string) => {
    Alert.alert('Delete expense', 'Are you sure?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await deleteExpense(id); fetchExpenses(); }
        catch { Alert.alert('Error', 'Failed to delete expense.'); }
      }},
    ]);
  };

  const total = expenses.reduce((sum, e) => sum + e.amount, 0);

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
            onEndEditing={fetchExpenses}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={c.placeholder}
          />
          <Text style={[styles.arrow, { color: c.textMuted }]}>→</Text>
          <TextInput
            style={[styles.dateInput, { backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]}
            value={endDate}
            onChangeText={setEndDate}
            onEndEditing={fetchExpenses}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={c.placeholder}
          />
          <TouchableOpacity style={[styles.refreshBtn, { backgroundColor: c.accent }]} onPress={fetchExpenses}>
            <Ionicons name="refresh" size={16} color="#ffffff" />
          </TouchableOpacity>
        </View>

        {/* Total bar */}
        <View style={[styles.totalBar, { backgroundColor: c.surface, borderBottomColor: c.border }]}>
          <View>
            <Text style={[styles.totalLabel, { color: c.textMuted }]}>Total spent</Text>
            <Text style={[styles.totalCount, { color: c.textMuted }]}>{expenses.length} transaction{expenses.length !== 1 ? 's' : ''}</Text>
          </View>
          <Text style={[styles.totalAmount, { color: c.accent }]}>€{total.toFixed(2)}</Text>
        </View>

        {loading ? (
          <ActivityIndicator style={{ flex: 1 }} color={c.accent} />
        ) : (
          <FlatList
            data={expenses}
            keyExtractor={(item) => item.id}
            contentContainerStyle={{ flexGrow: 1, paddingVertical: 8 }}
            ListEmptyComponent={
              <View style={styles.emptyWrap}>
                <Ionicons name="wallet-outline" size={40} color={c.textFaint} />
                <Text style={[styles.empty, { color: c.textMuted }]}>No expenses in this period</Text>
              </View>
            }
            renderItem={({ item }) => (
              <View style={[styles.card, { backgroundColor: c.surface, borderColor: c.border, borderLeftColor: categoryColor(item.category) }]}>
                <View style={styles.cardLeft}>
                  <View style={[styles.catDot, { backgroundColor: categoryColor(item.category) }]} />
                  <View style={styles.cardInfo}>
                    <Text style={[styles.rowCategory, { color: c.text }]}>{item.category}</Text>
                    <Text style={[styles.rowDate, { color: c.textMuted }]}>{item.date}</Text>
                    {item.description ? <Text style={[styles.rowDesc, { color: c.textFaint }]}>{item.description}</Text> : null}
                  </View>
                </View>
                <View style={styles.cardRight}>
                  <Text style={[styles.rowAmount, { color: c.text }]}>€{item.amount.toFixed(2)}</Text>
                  <View style={styles.actions}>
                    <TouchableOpacity onPress={() => openEdit(item)} style={styles.iconBtn} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                      <Ionicons name="pencil-outline" size={16} color={c.textMuted} />
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => handleDelete(item.id)} style={styles.iconBtn} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                      <Ionicons name="trash-outline" size={16} color={c.danger} />
                    </TouchableOpacity>
                  </View>
                </View>
              </View>
            )}
          />
        )}

        {/* Form */}
        {showForm && (
          <View style={[styles.form, { backgroundColor: c.surface, borderTopColor: c.border }]}>
            <Text style={[styles.formTitle, { color: c.text }]}>{editingId ? 'Edit Expense' : 'New Expense'}</Text>
            <TextInput
              style={[styles.input, { backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]}
              placeholder="Amount (e.g. 12.50)"
              keyboardType="decimal-pad"
              value={form.amount}
              onChangeText={(v) => setForm((f) => ({ ...f, amount: v }))}
              placeholderTextColor={c.placeholder}
            />
            <TextInput
              style={[styles.input, { backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]}
              placeholder="Category (e.g. Food, Fitness)"
              value={form.category}
              onChangeText={(v) => setForm((f) => ({ ...f, category: v }))}
              placeholderTextColor={c.placeholder}
            />
            <TextInput
              style={[styles.input, { backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]}
              placeholder="Description (optional)"
              value={form.description}
              onChangeText={(v) => setForm((f) => ({ ...f, description: v }))}
              placeholderTextColor={c.placeholder}
            />
            <TextInput
              style={[styles.input, { backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]}
              placeholder="Date (YYYY-MM-DD)"
              value={form.transaction_date}
              onChangeText={(v) => setForm((f) => ({ ...f, transaction_date: v }))}
              placeholderTextColor={c.placeholder}
            />
            <View style={styles.formActions}>
              <TouchableOpacity style={[styles.cancelBtn, { backgroundColor: c.cancelBg }]} onPress={closeForm}>
                <Text style={[styles.cancelBtnText, { color: c.cancelText }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.saveBtn, { backgroundColor: c.accent }]} onPress={handleSave}>
                <Text style={styles.saveBtnText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {!showForm && (
          <TouchableOpacity style={[styles.fab, { backgroundColor: c.accent, shadowColor: c.accent }]} onPress={openAdd}>
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
    totalBar: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      paddingHorizontal: 16,
      paddingVertical: 14,
      borderBottomWidth: StyleSheet.hairlineWidth,
    },
    totalLabel: { fontSize: 13, fontWeight: '500' },
    totalCount: { fontSize: 12, marginTop: 2 },
    totalAmount: { fontSize: 28, fontWeight: '800', letterSpacing: -0.5 },

    card: {
      flexDirection: 'row',
      alignItems: 'center',
      marginHorizontal: 12,
      marginVertical: 4,
      borderRadius: 14,
      borderWidth: 1,
      borderLeftWidth: 4,
      paddingVertical: 12,
      paddingHorizontal: 14,
      elevation: 2,
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.08,
      shadowRadius: 3,
    },
    cardLeft: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12 },
    catDot: { width: 8, height: 8, borderRadius: 4, flexShrink: 0 },
    cardInfo: { flex: 1 },
    rowCategory: { fontSize: 15, fontWeight: '600' },
    rowDate: { fontSize: 12, marginTop: 2 },
    rowDesc: { fontSize: 12, marginTop: 1 },
    cardRight: { alignItems: 'flex-end', gap: 6 },
    rowAmount: { fontSize: 17, fontWeight: '700' },
    actions: { flexDirection: 'row', gap: 4 },
    iconBtn: { padding: 4 },

    emptyWrap: { alignItems: 'center', marginTop: 80, gap: 12 },
    empty: { fontSize: 15 },

    form: {
      padding: 16,
      borderTopWidth: StyleSheet.hairlineWidth,
    },
    formTitle: { fontSize: 17, fontWeight: '700', marginBottom: 14 },
    input: {
      borderRadius: 12,
      paddingHorizontal: 14,
      paddingVertical: 12,
      fontSize: 15,
      marginBottom: 10,
      borderWidth: 1,
    },
    formActions: { flexDirection: 'row', gap: 10, marginTop: 4 },
    cancelBtn: { flex: 1, paddingVertical: 14, borderRadius: 12, alignItems: 'center' },
    cancelBtnText: { fontSize: 15, fontWeight: '600' },
    saveBtn: { flex: 1, paddingVertical: 14, borderRadius: 12, alignItems: 'center' },
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
