import { useEffect, useMemo, useRef, useState } from 'react';
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
import Markdown from 'react-native-markdown-display';
import { useLocalSearchParams } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import { sendChatMessage, uploadFile, type ReceiptItem } from '../src/api';
import { useTheme, type ThemeColors } from '../src/theme';
import FileContextBar from '../src/components/FileContextBar';
import ReceiptProposalCard from '../src/components/ReceiptProposalCard';

type Message = {
  role: 'user' | 'assistant';
  content: string;
  metadata?: { tools_executed: string[]; receipt_proposal?: ReceiptItem[] };
};

export default function ChatScreen() {
  const { theme } = useTheme();
  const c = theme.colors;
  const styles = useMemo(() => makeStyles(c), [theme]);
  const mdStyles = useMemo(() => makeMdStyles(c), [theme]);
  const scrollRef = useRef<ScrollView>(null);

  const params = useLocalSearchParams<{ fileId?: string; fileName?: string }>();

  const [inputText, setInputText] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeFileIds, setActiveFileIds] = useState<string[]>([]);
  const [activeFileNames, setActiveFileNames] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);

  // Accept fileId from Files screen "Ask about this"
  useEffect(() => {
    if (params.fileId && !activeFileIds.includes(params.fileId)) {
      setActiveFileIds((prev) => [...prev, params.fileId!]);
      setActiveFileNames((prev) => [...prev, params.fileName ?? params.fileId!]);
    }
  }, [params.fileId]);

  useEffect(() => {
    scrollRef.current?.scrollToEnd({ animated: true });
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!inputText.trim()) return;
    const userMessage: Message = { role: 'user', content: inputText };
    const newHistory = [...messages, userMessage];
    setMessages(newHistory);
    setInputText('');
    setIsLoading(true);
    const aiResponse = await sendChatMessage(inputText, { file_ids: activeFileIds.length ? activeFileIds : undefined });
    setMessages([...newHistory, aiResponse as Message]);
    setIsLoading(false);
  };

  const handleAttach = () => {
    Alert.alert('Attach file', 'Choose source', [
      { text: 'Camera', onPress: attachFromCamera },
      { text: 'Photo Library', onPress: attachFromLibrary },
      { text: 'Browse Files', onPress: attachDocument },
      { text: 'Cancel', style: 'cancel' },
    ]);
  };

  const _upload = async (uri: string, name: string, mimeType: string) => {
    setUploading(true);
    try {
      const uploaded = await uploadFile(uri, name, mimeType);
      setActiveFileIds((prev) => [...prev, uploaded.id]);
      setActiveFileNames((prev) => [...prev, uploaded.original_name]);
    } catch {
      Alert.alert('Error', 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const attachFromCamera = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') { Alert.alert('Permission needed', 'Allow camera access.'); return; }
    const result = await ImagePicker.launchCameraAsync({ quality: 0.8 });
    if (result.canceled || !result.assets?.[0]) return;
    const asset = result.assets[0];
    await _upload(asset.uri, asset.fileName ?? `photo_${Date.now()}.jpg`, asset.mimeType ?? 'image/jpeg');
  };

  const attachFromLibrary = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') { Alert.alert('Permission needed', 'Allow photo library access.'); return; }
    const result = await ImagePicker.launchImageLibraryAsync({ quality: 0.8 });
    if (result.canceled || !result.assets?.[0]) return;
    const asset = result.assets[0];
    await _upload(asset.uri, asset.fileName ?? `photo_${Date.now()}.jpg`, asset.mimeType ?? 'image/jpeg');
  };

  const attachDocument = async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'text/plain',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel'],
      copyToCacheDirectory: true,
    });
    if (result.canceled || !result.assets?.[0]) return;
    const asset = result.assets[0];
    await _upload(asset.uri, asset.name, asset.mimeType ?? 'application/octet-stream');
  };

  const removeFile = (id: string) => {
    const idx = activeFileIds.indexOf(id);
    setActiveFileIds((prev) => prev.filter((_, i) => i !== idx));
    setActiveFileNames((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: c.background }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 60 : 0}
    >
      <SafeAreaView style={{ flex: 1 }} edges={['bottom', 'left', 'right']}>

        <ScrollView
          ref={scrollRef}
          style={styles.chatArea}
          contentContainerStyle={{ padding: 16, flexGrow: 1 }}
          keyboardShouldPersistTaps="handled"
        >
          {messages.map((msg, i) => (
            <View
              key={i}
              style={[styles.bubble, msg.role === 'user' ? styles.userBubble : styles.aiBubble]}
            >
              {msg.role === 'user' ? (
                <Text style={styles.userText}>{msg.content}</Text>
              ) : (
                <Markdown style={mdStyles}>{msg.content}</Markdown>
              )}
              {msg.metadata?.receipt_proposal && msg.metadata.receipt_proposal.length > 0 && (
                <ReceiptProposalCard
                  items={msg.metadata.receipt_proposal}
                  onConfirmed={() => {}}
                />
              )}
              {msg.metadata && msg.metadata.tools_executed.length > 0 && (
                <View style={styles.toolBadge}>
                  <Text style={styles.toolBadgeText}>
                    ⚙️ {msg.metadata.tools_executed.join(', ')}
                  </Text>
                </View>
              )}
            </View>
          ))}
          {isLoading && (
            <View style={[styles.bubble, styles.aiBubble]}>
              <ActivityIndicator color={c.textMuted} />
            </View>
          )}
        </ScrollView>

        <FileContextBar
          fileIds={activeFileIds}
          fileNames={activeFileNames}
          onRemove={removeFile}
          onClearAll={() => { setActiveFileIds([]); setActiveFileNames([]); }}
        />

        <View style={styles.inputArea}>
          <TouchableOpacity
            style={[styles.attachBtn, uploading && { opacity: 0.5 }]}
            onPress={handleAttach}
            disabled={uploading}
          >
            {uploading
              ? <ActivityIndicator size="small" color={c.accent} />
              : <Text style={[styles.attachIcon, { color: c.accent }]}>📎</Text>}
          </TouchableOpacity>
          <TextInput
            style={styles.input}
            value={inputText}
            onChangeText={setInputText}
            placeholder="Message..."
            placeholderTextColor={c.placeholder}
            multiline
          />
          <TouchableOpacity
            style={[styles.sendBtn, !inputText.trim() && styles.sendBtnDisabled]}
            onPress={handleSend}
            disabled={!inputText.trim()}
          >
            <Text style={styles.sendBtnText}>Send</Text>
          </TouchableOpacity>
        </View>

      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

function makeStyles(c: ThemeColors) {
  return StyleSheet.create({
    chatArea: { flex: 1 },
    bubble: { padding: 14, borderRadius: 20, marginBottom: 10, maxWidth: '85%' },
    userBubble: { backgroundColor: c.userBubble, alignSelf: 'flex-end', borderBottomRightRadius: 4 },
    aiBubble: { backgroundColor: c.aiBubble, alignSelf: 'flex-start', borderBottomLeftRadius: 4 },
    userText: { color: '#ffffff', fontSize: 16 },
    toolBadge: { marginTop: 8, backgroundColor: c.drawerActiveBg, paddingVertical: 4, paddingHorizontal: 8, borderRadius: 12, alignSelf: 'flex-start' },
    toolBadgeText: { fontSize: 12, color: c.accent, fontWeight: '600' },
    inputArea: { flexDirection: 'row', alignItems: 'center', padding: 10, backgroundColor: c.surface, borderTopWidth: StyleSheet.hairlineWidth, borderColor: c.border, gap: 8 },
    attachBtn: { width: 40, height: 40, justifyContent: 'center', alignItems: 'center' },
    attachIcon: { fontSize: 22 },
    input: { flex: 1, backgroundColor: c.inputBg, borderRadius: 22, paddingHorizontal: 16, paddingVertical: 10, fontSize: 16, color: c.text, maxHeight: 120 },
    sendBtn: { backgroundColor: c.accent, borderRadius: 22, justifyContent: 'center', paddingHorizontal: 18, height: 44 },
    sendBtnDisabled: { opacity: 0.45 },
    sendBtnText: { color: '#ffffff', fontSize: 16, fontWeight: '600' },
  });
}

function makeMdStyles(c: ThemeColors) {
  return {
    body: { color: c.aiBubbleText, fontSize: 16, lineHeight: 24 },
    strong: { fontWeight: 'bold' as const },
    em: { fontStyle: 'italic' as const },
    bullet_list: { marginTop: 4, marginBottom: 4 },
    list_item: { marginVertical: 2 },
    code_inline: { backgroundColor: c.surfaceVariant, borderRadius: 4, paddingHorizontal: 5, fontFamily: 'monospace', color: c.text },
    fence: { backgroundColor: c.surfaceVariant, borderRadius: 6, padding: 10, color: c.text },
  };
}
