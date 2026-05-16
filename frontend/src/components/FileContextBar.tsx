import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
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
          <View key={id} style={[styles.chip, { backgroundColor: c.drawerActiveBg }]}>
            <Text style={[styles.chipText, { color: c.accent }]} numberOfLines={1}>{fileNames[i] ?? id}</Text>
            <TouchableOpacity onPress={() => onRemove(id)} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
              <Text style={[styles.x, { color: c.accent }]}>✕</Text>
            </TouchableOpacity>
          </View>
        ))}
      </ScrollView>
      <TouchableOpacity onPress={onClearAll} style={styles.clearBtn}>
        <Text style={[styles.clearText, { color: c.textMuted }]}>Clear</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'center', borderTopWidth: StyleSheet.hairlineWidth, paddingVertical: 6, paddingHorizontal: 8 },
  chips: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  chip: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14, gap: 6, maxWidth: 160 },
  chipText: { fontSize: 12, fontWeight: '600', flexShrink: 1 },
  x: { fontSize: 11, fontWeight: '700' },
  clearBtn: { paddingHorizontal: 10, paddingVertical: 4 },
  clearText: { fontSize: 12 },
});
