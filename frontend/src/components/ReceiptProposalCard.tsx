import { useState } from 'react';
import { Alert, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { createExpensesBulk, type ReceiptItem } from '../api';
import { useTheme } from '../theme';

type Props = {
  items: ReceiptItem[];
  onConfirmed: () => void;
};

export default function ReceiptProposalCard({ items, onConfirmed }: Props) {
  const { theme } = useTheme();
  const c = theme.colors;
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);

  const total = items.reduce((s, i) => s + i.amount, 0);

  const handleConfirmAll = async () => {
    setLoading(true);
    try {
      await createExpensesBulk(items);
      setConfirmed(true);
      onConfirmed();
    } catch {
      Alert.alert('Error', 'Failed to save expenses.');
    } finally {
      setLoading(false);
    }
  };

  if (confirmed) {
    return (
      <View style={[styles.card, { backgroundColor: c.surfaceVariant, borderColor: '#34c759' }]}>
        <Text style={{ color: '#34c759', fontWeight: '700', fontSize: 15 }}>
          ✅ {items.length} expense{items.length !== 1 ? 's' : ''} saved!
        </Text>
      </View>
    );
  }

  return (
    <View style={[styles.card, { backgroundColor: c.surfaceVariant, borderColor: c.border }]}>
      <Text style={[styles.title, { color: c.text }]}>🧾 Found {items.length} item{items.length !== 1 ? 's' : ''} on this receipt:</Text>

      {items.map((item, i) => (
        <View key={i} style={[styles.row, { borderBottomColor: c.borderLight }]}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.desc, { color: c.text }]}>{item.description}</Text>
            <Text style={[styles.cat, { color: c.textMuted }]}>{item.category}</Text>
          </View>
          <Text style={[styles.amount, { color: c.textSecondary }]}>€{item.amount.toFixed(2)}</Text>
        </View>
      ))}

      <View style={[styles.totalRow, { borderTopColor: c.border }]}>
        <Text style={[styles.totalLabel, { color: c.textMuted }]}>Total</Text>
        <Text style={[styles.totalAmount, { color: c.accent }]}>€{total.toFixed(2)}</Text>
      </View>

      <TouchableOpacity
        style={[styles.confirmBtn, { backgroundColor: c.accent, opacity: loading ? 0.6 : 1 }]}
        onPress={handleConfirmAll}
        disabled={loading}
      >
        <Text style={styles.confirmBtnText}>{loading ? 'Saving…' : 'Confirm All'}</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: 12, borderWidth: 1, padding: 14, marginTop: 10 },
  title: { fontSize: 14, fontWeight: '700', marginBottom: 10 },
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  desc: { fontSize: 13, fontWeight: '600' },
  cat: { fontSize: 11, marginTop: 1 },
  amount: { fontSize: 14, fontWeight: '600' },
  totalRow: { flexDirection: 'row', justifyContent: 'space-between', paddingTop: 10, marginTop: 4, borderTopWidth: StyleSheet.hairlineWidth },
  totalLabel: { fontSize: 13, fontWeight: '600' },
  totalAmount: { fontSize: 15, fontWeight: '700' },
  confirmBtn: { marginTop: 14, paddingVertical: 12, borderRadius: 10, alignItems: 'center' },
  confirmBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
