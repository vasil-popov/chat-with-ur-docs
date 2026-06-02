import { useState } from 'react';
import { Alert, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
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
      <View style={[styles.card, { backgroundColor: c.surfaceVariant, borderColor: c.success + '44' }]}>
        <View style={styles.confirmedRow}>
          <Ionicons name="checkmark-circle" size={20} color={c.success} />
          <Text style={[styles.confirmedText, { color: c.success }]}>
            {items.length} expense{items.length !== 1 ? 's' : ''} saved!
          </Text>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.card, { backgroundColor: c.surfaceVariant, borderColor: c.border }]}>
      {/* Header strip */}
      <View style={[styles.header, { backgroundColor: c.accent + '1a' }]}>
        <Ionicons name="receipt-outline" size={16} color={c.accent} />
        <Text style={[styles.headerText, { color: c.accent }]}>
          {items.length} item{items.length !== 1 ? 's' : ''} found on receipt
        </Text>
      </View>

      {items.map((item, i) => (
        <View key={i} style={[styles.row, { borderBottomColor: c.borderLight }]}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.desc, { color: c.text }]}>{item.description}</Text>
            <Text style={[styles.cat, { color: c.textMuted }]}>{item.category}</Text>
          </View>
          <Text style={[styles.amount, { color: c.accent }]}>€{item.amount.toFixed(2)}</Text>
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
        {loading
          ? <Text style={styles.confirmBtnText}>Saving…</Text>
          : (
            <>
              <Ionicons name="checkmark" size={16} color="#ffffff" />
              <Text style={styles.confirmBtnText}>Confirm All</Text>
            </>
          )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: 14, borderWidth: 1, overflow: 'hidden', marginTop: 10 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  headerText: { fontSize: 13, fontWeight: '700' },
  confirmedRow: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 14 },
  confirmedText: { fontSize: 15, fontWeight: '700' },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  desc: { fontSize: 13, fontWeight: '600' },
  cat: { fontSize: 11, marginTop: 2 },
  amount: { fontSize: 14, fontWeight: '700' },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  totalLabel: { fontSize: 13, fontWeight: '600' },
  totalAmount: { fontSize: 16, fontWeight: '800' },
  confirmBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 14,
    marginBottom: 14,
    marginTop: 4,
    paddingVertical: 13,
    borderRadius: 12,
    gap: 6,
  },
  confirmBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
