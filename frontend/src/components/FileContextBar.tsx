import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../theme';

type Props = {
  fileIds: string[];
  fileNames: string[];
  onRemove: (id: string) => void;
  onClearAll: () => void;
};

export default function FileContextBar({ fileIds, fileNames, onRemove, onClearAll }: Props) {
  const { theme } = useTheme();
  const c = theme.colors;

  if (fileIds.length === 0) return null;

  return (
    <View style={[styles.container, { backgroundColor: c.surface, borderTopColor: c.border }]}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
        {fileIds.map((id, i) => (
          <View key={id} style={[styles.chip, { backgroundColor: c.surfaceVariant, borderColor: c.accent }]}>
            <Ionicons name="attach" size={12} color={c.accent} />
            <Text style={[styles.chipText, { color: c.accent }]} numberOfLines={1}>{fileNames[i] ?? id}</Text>
            <TouchableOpacity onPress={() => onRemove(id)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name="close" size={13} color={c.textMuted} />
            </TouchableOpacity>
          </View>
        ))}
      </ScrollView>
      <TouchableOpacity onPress={onClearAll} style={styles.clearBtn}>
        <Text style={[styles.clearText, { color: c.textMuted }]}>Clear all</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingVertical: 8,
    paddingHorizontal: 8,
  },
  chips: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    gap: 5,
    maxWidth: 180,
  },
  chipText: { fontSize: 12, fontWeight: '600', flexShrink: 1 },
  clearBtn: { paddingHorizontal: 12, paddingVertical: 4 },
  clearText: { fontSize: 12, fontWeight: '500' },
});
