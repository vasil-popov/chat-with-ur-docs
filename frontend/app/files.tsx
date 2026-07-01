import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import { Ionicons } from '@expo/vector-icons';
import { useTheme, type ThemeColors } from '../src/theme';
import { type ReceiptItem, type UploadedFile, deleteFile, getFiles, uploadFile } from '../src/api';
import ReceiptProposalCard from '../src/components/ReceiptProposalCard';
import ActionSheet from '../src/components/ActionSheet';
import { alertMessage, confirmDestructive } from '../src/utils/alert';

const CATEGORIES = ['all', 'general', 'receipt', 'document', 'spreadsheet', 'image'] as const;
type Category = (typeof CATEGORIES)[number];

const FILE_TYPE_ICON: Record<string, { name: string; color: string }> = {
  image:  { name: 'image-outline',         color: '#10b981' },
  pdf:    { name: 'document-text-outline', color: '#ef4444' },
  txt:    { name: 'document-outline',      color: '#6a6a8a' },
  excel:  { name: 'grid-outline',          color: '#22c55e' },
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FilesScreen() {
  const { theme } = useTheme();
  const c = theme.colors;
  const styles = useMemo(() => makeStyles(c), [theme]);

  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [activeCategory, setActiveCategory] = useState<Category>('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showActionSheet, setShowActionSheet] = useState(false);
  const [receiptProposal, setReceiptProposal] = useState<{ fileName: string; items: ReceiptItem[] } | null>(null);

  useEffect(() => { fetchFiles(); }, [activeCategory]);

  const fetchFiles = async () => {
    setLoading(true);
    try {
      setFiles(await getFiles(activeCategory === 'all' ? undefined : activeCategory));
    } catch {
      alertMessage('Error', 'Could not load files.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = (id: string, name: string) => {
    confirmDestructive('Delete file', `Delete "${name}"?`, 'Delete', async () => {
      try { await deleteFile(id); fetchFiles(); }
      catch { alertMessage('Error', 'Failed to delete file.'); }
    });
  };

  const handleUploadResult = async (uri: string, name: string, mimeType: string) => {
    setUploading(true);
    try {
      const uploaded = await uploadFile(uri, name, mimeType);
      setFiles((prev) => [uploaded, ...prev]);
      if (uploaded.is_receipt && uploaded.receipt_proposal?.length) {
        setReceiptProposal({ fileName: uploaded.original_name, items: uploaded.receipt_proposal });
      }
    } catch (err) {
      alertMessage('Error', err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const pickDocument = async () => {
    setShowActionSheet(false);
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'text/plain',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel'],
      copyToCacheDirectory: true,
    });
    if (result.canceled || !result.assets?.[0]) return;
    const asset = result.assets[0];
    await handleUploadResult(asset.uri, asset.name, asset.mimeType ?? 'application/octet-stream');
  };

  const pickImage = async () => {
    setShowActionSheet(false);
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') { alertMessage('Permission needed', 'Allow photo library access.'); return; }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (result.canceled || !result.assets?.[0]) return;
    const asset = result.assets[0];
    const name = asset.fileName ?? `photo_${Date.now()}.jpg`;
    await handleUploadResult(asset.uri, name, asset.mimeType ?? 'image/jpeg');
  };

  const openCamera = async () => {
    setShowActionSheet(false);
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') { alertMessage('Permission needed', 'Allow camera access.'); return; }
    const result = await ImagePicker.launchCameraAsync({ quality: 0.8 });
    if (result.canceled || !result.assets?.[0]) return;
    const asset = result.assets[0];
    const name = asset.fileName ?? `photo_${Date.now()}.jpg`;
    await handleUploadResult(asset.uri, name, asset.mimeType ?? 'image/jpeg');
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: c.background }]} edges={['bottom', 'left', 'right']}>

      {/* Category chips */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={[styles.chipRow, { backgroundColor: c.surface, borderBottomColor: c.border }]}
        contentContainerStyle={styles.chipContent}
      >
        {CATEGORIES.map((cat) => (
          <TouchableOpacity
            key={cat}
            style={[
              styles.chip,
              { borderColor: activeCategory === cat ? c.accent : c.border },
              activeCategory === cat && { backgroundColor: c.accent },
            ]}
            onPress={() => setActiveCategory(cat)}
          >
            <Text style={[styles.chipText, { color: activeCategory === cat ? '#ffffff' : c.textMuted }]}>
              {cat.charAt(0).toUpperCase() + cat.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Receipt proposal card */}
      {receiptProposal && (
        <View style={{ paddingHorizontal: 12, paddingTop: 8 }}>
          <Text style={{ fontSize: 12, color: c.textMuted, marginBottom: 4 }}>
            From: {receiptProposal.fileName}
          </Text>
          <ReceiptProposalCard
            items={receiptProposal.items}
            onConfirmed={() => setReceiptProposal(null)}
          />
        </View>
      )}

      {/* File list */}
      {loading ? (
        <ActivityIndicator style={{ flex: 1 }} color={c.accent} />
      ) : (
        <ScrollView style={{ flex: 1 }}>
          {files.length === 0 && (
            <View style={styles.emptyWrap}>
              <Ionicons name="folder-open-outline" size={40} color={c.textFaint} />
              <Text style={[styles.empty, { color: c.textMuted }]}>No files yet. Tap + to upload.</Text>
            </View>
          )}
          {files.map((f) => {
            const iconInfo = FILE_TYPE_ICON[f.file_type] ?? { name: 'document-outline', color: c.textMuted };
            return (
              <View key={f.id} style={[styles.card, { backgroundColor: c.surface, borderColor: c.border }]}>
                <TouchableOpacity
                  style={styles.cardHeader}
                  onPress={() => setExpandedId(expandedId === f.id ? null : f.id)}
                >
                  <View style={[styles.fileIconBox, { backgroundColor: iconInfo.color + '22' }]}>
                    <Ionicons name={iconInfo.name as any} size={20} color={iconInfo.color} />
                  </View>
                  <View style={styles.fileInfo}>
                    <Text style={[styles.fileName, { color: c.text }]} numberOfLines={1}>{f.original_name}</Text>
                    <Text style={[styles.fileMeta, { color: c.textMuted }]}>
                      {formatSize(f.size_bytes)} · {f.uploaded_at.slice(0, 10)}
                      {f.is_receipt ? ' · Receipt' : ''}
                    </Text>
                  </View>
                  <View style={[styles.statusBadge, { backgroundColor: statusBg(f.status, c) }]}>
                    <Text style={[styles.statusText, { color: statusFg(f.status, c) }]}>{f.status}</Text>
                  </View>
                  <Ionicons
                    name={expandedId === f.id ? 'chevron-up' : 'chevron-down'}
                    size={14}
                    color={c.textMuted}
                    style={{ marginLeft: 6 }}
                  />
                </TouchableOpacity>

                {expandedId === f.id && (
                  <View style={[styles.expanded, { borderTopColor: c.borderLight }]}>
                    {f.extracted_text ? (
                      <ScrollView style={[styles.textPreview, { backgroundColor: c.surfaceVariant }]} nestedScrollEnabled>
                        <Text style={[styles.previewText, { color: c.textSecondary }]}>
                          {f.extracted_text.slice(0, 1500)}{f.extracted_text.length > 1500 ? '\n…' : ''}
                        </Text>
                      </ScrollView>
                    ) : (
                      <Text style={[styles.noText, { color: c.textMuted }]}>{f.error_message ?? 'No text extracted.'}</Text>
                    )}
                    <View style={styles.expandedActions}>
                      <TouchableOpacity
                        style={[styles.actionBtn, { backgroundColor: c.accent }]}
                        onPress={() => router.push({ pathname: '/', params: { fileId: f.id, fileName: f.original_name } })}
                      >
                        <Ionicons name="chatbubble-outline" size={14} color="#ffffff" />
                        <Text style={styles.actionBtnText}>Ask about this</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[styles.actionBtn, { backgroundColor: c.danger + '22', borderWidth: 1, borderColor: c.danger + '44' }]}
                        onPress={() => handleDelete(f.id, f.original_name)}
                      >
                        <Ionicons name="trash-outline" size={14} color={c.danger} />
                        <Text style={[styles.actionBtnText, { color: c.danger }]}>Delete</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                )}
              </View>
            );
          })}
          <View style={{ height: 90 }} />
        </ScrollView>
      )}

      {/* Action sheet overlay */}
      <ActionSheet
        visible={showActionSheet}
        title="Add File"
        onCancel={() => setShowActionSheet(false)}
        actions={[
          { label: 'Camera (receipt photo)', icon: 'camera-outline', onPress: openCamera },
          { label: 'Photo Library', icon: 'image-outline', onPress: pickImage },
          { label: 'Browse Files (PDF, TXT, Excel)', icon: 'folder-open-outline', onPress: pickDocument },
        ]}
      />

      {/* FAB */}
      {uploading ? (
        <View style={[styles.fab, { backgroundColor: c.surface }]}>
          <ActivityIndicator color={c.accent} />
        </View>
      ) : (
        <TouchableOpacity style={[styles.fab, { backgroundColor: c.accent, shadowColor: c.accent }]} onPress={() => setShowActionSheet(true)}>
          <Ionicons name="add" size={28} color="#ffffff" />
        </TouchableOpacity>
      )}
    </SafeAreaView>
  );
}

function statusBg(status: string, c: ThemeColors): string {
  if (status === 'ready') return c.success + '22';
  if (status === 'error') return c.danger + '22';
  return c.surfaceVariant;
}

function statusFg(status: string, c: ThemeColors): string {
  if (status === 'ready') return c.success;
  if (status === 'error') return c.danger;
  return c.textMuted;
}

function makeStyles(c: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1 },
    chipRow: { flexGrow: 0, borderBottomWidth: StyleSheet.hairlineWidth },
    chipContent: { paddingHorizontal: 12, paddingVertical: 10, gap: 8 },
    chip: {
      paddingHorizontal: 16,
      paddingVertical: 8,
      borderRadius: 20,
      borderWidth: 1,
    },
    chipText: { fontSize: 13, fontWeight: '600' },

    emptyWrap: { alignItems: 'center', marginTop: 80, gap: 12 },
    empty: { fontSize: 15 },

    card: {
      marginHorizontal: 12,
      marginTop: 8,
      borderRadius: 14,
      borderWidth: 1,
      overflow: 'hidden',
      elevation: 2,
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.08,
      shadowRadius: 3,
    },
    cardHeader: { flexDirection: 'row', alignItems: 'center', padding: 14, gap: 12 },
    fileIconBox: {
      width: 40,
      height: 40,
      borderRadius: 10,
      justifyContent: 'center',
      alignItems: 'center',
      flexShrink: 0,
    },
    fileInfo: { flex: 1 },
    fileName: { fontSize: 14, fontWeight: '600' },
    fileMeta: { fontSize: 12, marginTop: 2 },
    statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20 },
    statusText: { fontSize: 11, fontWeight: '700' },

    expanded: { padding: 12, borderTopWidth: StyleSheet.hairlineWidth },
    textPreview: { maxHeight: 200, borderRadius: 10, padding: 10, marginBottom: 10 },
    previewText: { fontSize: 12, lineHeight: 18 },
    noText: { fontSize: 13, marginBottom: 10 },
    expandedActions: { flexDirection: 'row', gap: 10 },
    actionBtn: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: 10,
      borderRadius: 10,
      gap: 6,
    },
    actionBtnText: { fontSize: 13, color: '#fff', fontWeight: '600' },

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
