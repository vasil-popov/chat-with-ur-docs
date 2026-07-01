import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme, type ThemeColors } from '../theme';

export type ActionSheetAction = {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
  destructive?: boolean;
};

type Props = {
  visible: boolean;
  title: string;
  actions: ActionSheetAction[];
  onCancel: () => void;
  cancelLabel?: string;
};

export default function ActionSheet({ visible, title, actions, onCancel, cancelLabel = 'Cancel' }: Props) {
  const { theme } = useTheme();
  const c = theme.colors;
  const styles = makeStyles(c);

  if (!visible) return null;

  return (
    <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={onCancel}>
      <View style={[styles.actionSheet, { backgroundColor: c.surface }]} accessibilityViewIsModal>
        <View style={[styles.sheetHandle, { backgroundColor: c.border }]} />
        <Text style={[styles.actionSheetTitle, { color: c.text }]}>{title}</Text>
        {actions.map((action) => (
          <TouchableOpacity
            key={action.label}
            style={[styles.sheetBtn, { backgroundColor: c.surfaceVariant }]}
            onPress={action.onPress}
            accessibilityRole="button"
            accessibilityLabel={action.label}
          >
            <Ionicons name={action.icon} size={20} color={action.destructive ? c.danger : c.accent} />
            <Text style={[styles.sheetBtnText, { color: action.destructive ? c.danger : c.text }]}>
              {action.label}
            </Text>
          </TouchableOpacity>
        ))}
        <TouchableOpacity
          style={[styles.sheetBtn, { backgroundColor: c.cancelBg }]}
          onPress={onCancel}
          accessibilityRole="button"
          accessibilityLabel={cancelLabel}
        >
          <Text style={[styles.sheetBtnText, { color: c.cancelText, textAlign: 'center' }]}>{cancelLabel}</Text>
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );
}

function makeStyles(c: ThemeColors) {
  return StyleSheet.create({
    overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end', zIndex: 100, elevation: 100 },
    actionSheet: {
      borderTopLeftRadius: 24,
      borderTopRightRadius: 24,
      padding: 16,
      paddingBottom: 36,
      gap: 10,
    },
    sheetHandle: {
      width: 36,
      height: 4,
      borderRadius: 2,
      alignSelf: 'center',
      marginBottom: 12,
    },
    actionSheetTitle: { fontSize: 17, fontWeight: '700', textAlign: 'center', marginBottom: 6 },
    sheetBtn: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingVertical: 14,
      paddingHorizontal: 16,
      borderRadius: 14,
      gap: 12,
    },
    sheetBtnText: { fontSize: 15, fontWeight: '500', flex: 1 },
  });
}
