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
import { useTheme, type ThemeColors } from '../src/theme';
import { type Expense, createExpense, deleteExpense, getExpenses, updateExpense } from '../src/api';

const today = new Date();
const todayStr = today.toISOString().split('T')[0];
const firstOfMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`;

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
      <SafeAreaView style={styles.container} edges={['bottom', 'left', 'right']}>

        <View style={styles.filterRow}>
          <TextInput style={styles.dateInput} value={startDate} onChangeText={setStartDate} onEndEditing={fetchExpenses} placeholder="YYYY-MM-DD" placeholderTextColor={c.placeholder} />
          <Text style={styles.arrow}>→</Text>
          <TextInput style={styles.dateInput} value={endDate} onChangeText={setEndDate} onEndEditing={fetchExpenses} placeholder="YYYY-MM-DD" placeholderTextColor={c.placeholder} />
          <TouchableOpacity style={styles.refreshBtn} onPress={fetchExpenses}>
            <Text style={styles.refreshIcon}>↻</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.totalBar}>
          <Text style={styles.totalLabel}>Total ({expenses.length} items)</Text>
          <Text style={styles.totalAmount}>€{total.toFixed(2)}</Text>
        </View>

        {loading ? (
          <ActivityIndicator style={{ flex: 1 }} color={c.accent} />
        ) : (
          <FlatList
            data={expenses}
            keyExtractor={(item) => item.id}
            contentContainerStyle={{ flexGrow: 1 }}
            ListEmptyComponent={<Text style={styles.empty}>No expenses in this period</Text>}
            renderItem={({ item }) => (
              <View style={styles.row}>
                <View style={styles.rowLeft}>
                  <Text style={styles.rowCategory}>{item.category}</Text>
                  <Text style={styles.rowDate}>{item.date}</Text>
                  {item.description ? <Text style={styles.rowDesc}>{item.description}</Text> : null}
                </View>
                <Text style={styles.rowAmount}>€{item.amount.toFixed(2)}</Text>
                <TouchableOpacity onPress={() => openEdit(item)} style={styles.iconBtn}>
                  <Text style={styles.icon}>✏️</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => handleDelete(item.id)} style={styles.iconBtn}>
                  <Text style={styles.icon}>🗑️</Text>
                </TouchableOpacity>
              </View>
            )}
          />
        )}

        {showForm && (
          <View style={styles.form}>
            <Text style={styles.formTitle}>{editingId ? 'Edit Expense' : 'New Expense'}</Text>
            <TextInput style={styles.input} placeholder="Amount (e.g. 12.50)" keyboardType="decimal-pad" value={form.amount} onChangeText={(v) => setForm((f) => ({ ...f, amount: v }))} placeholderTextColor={c.placeholder} />
            <TextInput style={styles.input} placeholder="Category (e.g. Food, Fitness)" value={form.category} onChangeText={(v) => setForm((f) => ({ ...f, category: v }))} placeholderTextColor={c.placeholder} />
            <TextInput style={styles.input} placeholder="Description (optional)" value={form.description} onChangeText={(v) => setForm((f) => ({ ...f, description: v }))} placeholderTextColor={c.placeholder} />
            <TextInput style={styles.input} placeholder="Date (YYYY-MM-DD)" value={form.transaction_date} onChangeText={(v) => setForm((f) => ({ ...f, transaction_date: v }))} placeholderTextColor={c.placeholder} />
            <View style={styles.formActions}>
              <TouchableOpacity style={styles.cancelBtn} onPress={closeForm}>
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.saveBtn} onPress={handleSave}>
                <Text style={styles.saveBtnText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {!showForm && (
          <TouchableOpacity style={styles.fab} onPress={openAdd}>
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
    totalBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, backgroundColor: c.surface, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: c.border },
    totalLabel: { fontSize: 14, color: c.textMuted },
    totalAmount: { fontSize: 18, fontWeight: '700', color: c.accent },
    row: { flexDirection: 'row', alignItems: 'center', padding: 14, backgroundColor: c.surface, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: c.borderLight },
    rowLeft: { flex: 1 },
    rowCategory: { fontSize: 15, fontWeight: '600', color: c.text },
    rowDate: { fontSize: 12, color: c.textMuted, marginTop: 2 },
    rowDesc: { fontSize: 12, color: c.textFaint, marginTop: 1 },
    rowAmount: { fontSize: 16, fontWeight: '600', marginRight: 4, color: c.textSecondary },
    iconBtn: { padding: 6 },
    icon: { fontSize: 16 },
    empty: { textAlign: 'center', marginTop: 60, color: c.textMuted, fontSize: 15 },
    form: { backgroundColor: c.surface, padding: 16, borderTopWidth: StyleSheet.hairlineWidth, borderColor: c.border },
    formTitle: { fontSize: 16, fontWeight: '600', marginBottom: 12, color: c.text },
    input: { backgroundColor: c.inputBg, borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10, fontSize: 15, marginBottom: 10, color: c.text },
    formActions: { flexDirection: 'row', gap: 10, marginTop: 4 },
    cancelBtn: { flex: 1, paddingVertical: 14, borderRadius: 10, backgroundColor: c.cancelBg, alignItems: 'center' },
    cancelBtnText: { fontSize: 15, color: c.cancelText },
    saveBtn: { flex: 1, paddingVertical: 14, borderRadius: 10, backgroundColor: c.accent, alignItems: 'center' },
    saveBtnText: { fontSize: 15, color: '#fff', fontWeight: '600' },
    fab: { position: 'absolute', bottom: 28, right: 24, width: 56, height: 56, borderRadius: 28, backgroundColor: c.accent, justifyContent: 'center', alignItems: 'center', elevation: 5, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.3, shadowRadius: 4 },
    fabText: { color: '#fff', fontSize: 30, lineHeight: 34 },
  });
}
