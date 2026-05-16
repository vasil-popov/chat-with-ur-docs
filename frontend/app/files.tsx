import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
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
import { useTheme, type ThemeColors } from '../src/theme';
import { type ReceiptItem, type UploadedFile, deleteFile, getFiles, uploadFile } from '../src/api';
import ReceiptProposalCard from '../src/components/ReceiptProposalCard';

const CATEGORIES = ['all', 'general', 'receipt', 'document', 'spreadsheet', 'image'] as const;
type Category = (typeof CATEGORIES)[number];

const FILE_ICONS: Record<string, string> = {
  image: '🖼️',
  pdf: '📄',
  txt: '📝',
  excel: '📊',
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
      Alert.alert('Error', 'Could not load files.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = (id: string, name: string) => {
    Alert.alert('Delete file', `Delete "${name}"?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive', onPress: async () => {
          try { await deleteFile(id); fetchFiles(); }
          catch { Alert.alert('Error', 'Failed to delete file.'); }
        },
      },
    ]);
  };

  const handleUploadResult = async (uri: string, name: string, mimeType: string) => {
    setUploading(true);
    try {
      const uploaded = await uploadFile(uri, name, mimeType);
      setFiles((prev) => [uploaded, ...prev]);
      if (uploaded.is_receipt && uploaded.receipt_proposal?.length) {
        setReceiptProposal({ fileName: uploaded.original_name, items: uploaded.receipt_proposal });
      }
    } catch {
      Alert.alert('Error', 'Upload failed.');
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
    if (status !== 'granted') { Alert.alert('Permission needed', 'Allow photo library access.'); return; }
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
    if (status !== 'granted') { Alert.alert('Permission needed', 'Allow camera access.'); return; }
    const result = await ImagePicker.launchCameraAsync({ quality: 0.8 });
    if (result.canceled || !result.assets?.[0]) return;
    const asset = result.assets[0];
    const name = asset.fileName ?? `photo_${Date.now()}.jpg`;
    await handleUploadResult(asset.uri, name, asset.mimeType ?? 'image/jpeg');
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom', 'left', 'right']}>

      {/* Category chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow} contentContainerStyle={styles.chipContent}>
        {CATEGORIES.map((cat) => (
          <TouchableOpacity
            key={cat}
            style={[styles.chip, activeCategory === cat && styles.chipActive]}
            onPress={() => setActiveCategory(cat)}
          >
            <Text style={[styles.chipText, activeCategory === cat && styles.chipTextActive]}>
              {cat.charAt(0).toUpperCase() + cat.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Receipt proposal card — shown immediately after upload */}
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
            <Text style={styles.empty}>No files yet. Tap + to upload.</Text>
          )}
          {files.map((f) => (
            <View key={f.id} style={styles.card}>
              <TouchableOpacity style={styles.cardHeader} onPress={() => setExpandedId(expandedId === f.id ? null : f.id)}>
                <Text style={styles.fileIcon}>{FILE_ICONS[f.file_type] ?? '📁'}</Text>
                <View style={styles.fileInfo}>
                  <Text style={styles.fileName} numberOfLines={1}>{f.original_name}</Text>
                  <Text style={styles.fileMeta}>
                    {formatSize(f.size_bytes)} · {f.uploaded_at.slice(0, 10)}
                    {f.is_receipt ? ' · 🧾 Receipt' : ''}
                  </Text>
                </View>
                <View style={[styles.statusBadge, { backgroundColor: statusColor(f.status, c) }]}>
                  <Text style={styles.statusText}>{f.status}</Text>
                </View>
              </TouchableOpacity>

              {expandedId === f.id && (
                <View style={styles.expanded}>
                  {f.extracted_text ? (
                    <ScrollView style={styles.textPreview} nestedScrollEnabled>
                      <Text style={styles.previewText}>{f.extracted_text.slice(0, 1500)}{f.extracted_text.length > 1500 ? '\n…' : ''}</Text>
                    </ScrollView>
                  ) : (
                    <Text style={styles.noText}>{f.error_message ?? 'No text extracted.'}</Text>
                  )}
                  <View style={styles.expandedActions}>
                    <TouchableOpacity
                      style={[styles.actionBtn, { backgroundColor: c.accent }]}
                      onPress={() => router.push({ pathname: '/', params: { fileId: f.id, fileName: f.original_name } })}
                    >
                      <Text style={styles.actionBtnText}>Ask about this</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.actionBtn, { backgroundColor: c.cancelBg }]}
                      onPress={() => handleDelete(f.id, f.original_name)}
                    >
                      <Text style={[styles.actionBtnText, { color: c.cancelText }]}>Delete</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              )}
            </View>
          ))}
          <View style={{ height: 90 }} />
        </ScrollView>
      )}

      {/* Action sheet overlay */}
      {showActionSheet && (
        <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={() => setShowActionSheet(false)}>
          <View style={styles.actionSheet}>
            <Text style={styles.actionSheetTitle}>Add File</Text>
            <TouchableOpacity style={styles.sheetBtn} onPress={openCamera}>
              <Text style={styles.sheetBtnText}>📷  Camera (receipt photo)</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.sheetBtn} onPress={pickImage}>
              <Text style={styles.sheetBtnText}>🖼️  Photo Library</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.sheetBtn} onPress={pickDocument}>
              <Text style={styles.sheetBtnText}>📁  Browse Files (PDF, TXT, Excel)</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.sheetBtn, styles.cancelSheetBtn]} onPress={() => setShowActionSheet(false)}>
              <Text style={[styles.sheetBtnText, { color: c.cancelText }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      )}

      {/* FAB */}
      {uploading ? (
        <View style={[styles.fab, { backgroundColor: c.surface }]}>
          <ActivityIndicator color={c.accent} />
        </View>
      ) : (
        <TouchableOpacity style={styles.fab} onPress={() => setShowActionSheet(true)}>
          <Text style={styles.fabText}>+</Text>
        </TouchableOpacity>
      )}
    </SafeAreaView>
  );
}

function statusColor(status: string, c: ThemeColors): string {
  if (status === 'ready') return '#34c759';
  if (status === 'error') return '#ff3b30';
  return c.textMuted;
}

function makeStyles(c: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: c.background },
    chipRow: { flexGrow: 0, backgroundColor: c.surface, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: c.border },
    chipContent: { paddingHorizontal: 12, paddingVertical: 10, gap: 8 },
    chip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 16, backgroundColor: c.inputBg },
    chipActive: { backgroundColor: c.accent },
    chipText: { fontSize: 13, color: c.textMuted },
    chipTextActive: { color: '#fff', fontWeight: '600' },
    empty: { textAlign: 'center', marginTop: 60, color: c.textMuted, fontSize: 15 },
    card: { backgroundColor: c.surface, marginTop: 8, marginHorizontal: 12, borderRadius: 12, overflow: 'hidden', elevation: 1, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 2 },
    cardHeader: { flexDirection: 'row', alignItems: 'center', padding: 12 },
    fileIcon: { fontSize: 28, marginRight: 12 },
    fileInfo: { flex: 1 },
    fileName: { fontSize: 14, fontWeight: '600', color: c.text },
    fileMeta: { fontSize: 12, color: c.textMuted, marginTop: 2 },
    statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 },
    statusText: { fontSize: 11, color: '#fff', fontWeight: '600' },
    expanded: { padding: 12, borderTopWidth: StyleSheet.hairlineWidth, borderColor: c.borderLight },
    textPreview: { maxHeight: 200, backgroundColor: c.surfaceVariant, borderRadius: 8, padding: 10, marginBottom: 10 },
    previewText: { fontSize: 12, color: c.textSecondary, lineHeight: 18 },
    noText: { fontSize: 13, color: c.textMuted, marginBottom: 10 },
    expandedActions: { flexDirection: 'row', gap: 10 },
    actionBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, alignItems: 'center' },
    actionBtnText: { fontSize: 14, color: '#fff', fontWeight: '600' },
    overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
    actionSheet: { backgroundColor: c.surface, borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 16, paddingBottom: 32 },
    actionSheetTitle: { fontSize: 16, fontWeight: '700', color: c.text, textAlign: 'center', marginBottom: 16 },
    sheetBtn: { paddingVertical: 14, borderRadius: 10, backgroundColor: c.inputBg, alignItems: 'center', marginBottom: 10 },
    cancelSheetBtn: { backgroundColor: c.cancelBg },
    sheetBtnText: { fontSize: 15, color: c.text, fontWeight: '500' },
    fab: { position: 'absolute', bottom: 28, right: 24, width: 56, height: 56, borderRadius: 28, backgroundColor: c.accent, justifyContent: 'center', alignItems: 'center', elevation: 5, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.3, shadowRadius: 4 },
    fabText: { color: '#fff', fontSize: 30, lineHeight: 34 },
  });
}
