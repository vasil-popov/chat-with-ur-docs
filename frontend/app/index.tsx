import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
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
import { Ionicons } from '@expo/vector-icons';
import { sendChatMessageStream, uploadFile, type ReceiptItem } from '../src/api';
import { useTheme, type ThemeColors } from '../src/theme';
import FileContextBar from '../src/components/FileContextBar';
import ReceiptProposalCard from '../src/components/ReceiptProposalCard';
import ActionSheet from '../src/components/ActionSheet';
import { alertMessage } from '../src/utils/alert';

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
  const [loadingTools, setLoadingTools] = useState<string[]>([]);
  const [activeFileIds, setActiveFileIds] = useState<string[]>([]);
  const [activeFileNames, setActiveFileNames] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [showAttachSheet, setShowAttachSheet] = useState(false);

  useEffect(() => {
    if (params.fileId && !activeFileIds.includes(params.fileId)) {
      setActiveFileIds((prev) => [...prev, params.fileId!]);
      setActiveFileNames((prev) => [...prev, params.fileName ?? params.fileId!]);
    }
  }, [params.fileId]);

  useEffect(() => {
    scrollRef.current?.scrollToEnd({ animated: true });
  }, [messages, isLoading, loadingTools]);

  const handleSend = async () => {
    if (!inputText.trim() || isLoading) return;

    const userMsg: Message = { role: 'user', content: inputText };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInputText('');
    setIsLoading(true);
    setLoadingTools([]);

    await sendChatMessageStream(
      inputText,
      { file_ids: activeFileIds.length ? activeFileIds : undefined },
      {
        onTool: (name) =>
          setLoadingTools((prev) => (prev.includes(name) ? prev : [...prev, name])),
        onDone: (content, tools) => {
          setMessages([...newHistory, { role: 'assistant', content, metadata: { tools_executed: tools } }]);
          setIsLoading(false);
          setLoadingTools([]);
        },
        onError: (err) => {
          setMessages([...newHistory, { role: 'assistant', content: `Error: ${err}`, metadata: { tools_executed: [] } }]);
          setIsLoading(false);
          setLoadingTools([]);
        },
      },
    );
  };

  const handleAttach = () => setShowAttachSheet(true);

  const _upload = async (uri: string, name: string, mimeType: string) => {
    setUploading(true);
    try {
      const uploaded = await uploadFile(uri, name, mimeType);
      setActiveFileIds((prev) => [...prev, uploaded.id]);
      setActiveFileNames((prev) => [...prev, uploaded.original_name]);

      if (uploaded.is_receipt && uploaded.receipt_proposal?.length) {
        const proposalMsg: Message = {
          role: 'assistant',
          content: `Receipt detected in **${uploaded.original_name}**. Review the items below and confirm to log them as expenses.`,
          metadata: { tools_executed: [], receipt_proposal: uploaded.receipt_proposal },
        };
        setMessages((prev) => [...prev, proposalMsg]);
      }
    } catch (err) {
      alertMessage('Error', err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const attachFromCamera = async () => {
    setShowAttachSheet(false);
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') { alertMessage('Permission needed', 'Allow camera access.'); return; }
    const result = await ImagePicker.launchCameraAsync({ quality: 0.8 });
    if (result.canceled || !result.assets?.[0]) return;
    const a = result.assets[0];
    await _upload(a.uri, a.fileName ?? `photo_${Date.now()}.jpg`, a.mimeType ?? 'image/jpeg');
  };

  const attachFromLibrary = async () => {
    setShowAttachSheet(false);
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') { alertMessage('Permission needed', 'Allow photo library access.'); return; }
    const result = await ImagePicker.launchImageLibraryAsync({ quality: 0.8 });
    if (result.canceled || !result.assets?.[0]) return;
    const a = result.assets[0];
    await _upload(a.uri, a.fileName ?? `photo_${Date.now()}.jpg`, a.mimeType ?? 'image/jpeg');
  };

  const attachDocument = async () => {
    setShowAttachSheet(false);
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'text/plain',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel'],
      copyToCacheDirectory: true,
    });
    if (result.canceled || !result.assets?.[0]) return;
    const a = result.assets[0];
    await _upload(a.uri, a.name, a.mimeType ?? 'application/octet-stream');
  };

  const removeFile = (id: string) => {
    const idx = activeFileIds.indexOf(id);
    setActiveFileIds((prev) => prev.filter((_, i) => i !== idx));
    setActiveFileNames((prev) => prev.filter((_, i) => i !== idx));
  };

  const canSend = inputText.trim().length > 0 && !isLoading;

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
          {messages.length === 0 && !isLoading && (
            <View style={styles.emptyState}>
              <View style={[styles.emptyIcon, { backgroundColor: c.accent }]}>
                <Ionicons name="sparkles" size={32} color="#ffffff" />
              </View>
              <Text style={[styles.emptyTitle, { color: c.text }]}>Ask me anything</Text>
              <Text style={[styles.emptySubtitle, { color: c.textMuted }]}>
                Chat with your documents, track expenses, log workouts, or just ask a question.
              </Text>
            </View>
          )}

          {messages.map((msg, i) => (
            <View key={i} style={msg.role === 'user' ? styles.userRow : styles.aiRow}>
              {msg.role === 'assistant' && (
                <View style={[styles.aiAvatar, { backgroundColor: c.accent }]}>
                  <Ionicons name="sparkles" size={12} color="#ffffff" />
                </View>
              )}
              <View style={[
                styles.bubble,
                msg.role === 'user' ? styles.userBubble : styles.aiBubble,
              ]}>
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
                  <View style={[styles.toolBadge, { backgroundColor: c.drawerActiveBg }]}>
                    <View style={[styles.toolDot, { backgroundColor: c.accent }]} />
                    <Text style={[styles.toolBadgeText, { color: c.accent }]}>
                      {msg.metadata.tools_executed.join(' · ')}
                    </Text>
                  </View>
                )}
              </View>
            </View>
          ))}

          {isLoading && (
            <View style={styles.aiRow}>
              <View style={[styles.aiAvatar, { backgroundColor: c.accent }]}>
                <Ionicons name="sparkles" size={12} color="#ffffff" />
              </View>
              <View style={[styles.bubble, styles.aiBubble, styles.loadingBubble]}>
                <ActivityIndicator color={c.accent} size="small" />
                {loadingTools.length > 0 && (
                  <Text style={[styles.loadingToolText, { color: c.textMuted }]}>
                    {loadingTools.join(' · ')}
                  </Text>
                )}
              </View>
            </View>
          )}
        </ScrollView>

        <FileContextBar
          fileIds={activeFileIds}
          fileNames={activeFileNames}
          onRemove={removeFile}
          onClearAll={() => { setActiveFileIds([]); setActiveFileNames([]); }}
        />

        <View style={[styles.inputArea, { backgroundColor: c.surface, borderTopColor: c.border }]}>
          <TouchableOpacity
            style={[styles.attachBtn, { backgroundColor: c.surfaceVariant }, uploading && { opacity: 0.5 }]}
            onPress={handleAttach}
            disabled={uploading}
          >
            {uploading
              ? <ActivityIndicator size="small" color={c.accent} />
              : <Ionicons name="attach" size={20} color={c.textMuted} />}
          </TouchableOpacity>
          <TextInput
            style={[styles.input, { backgroundColor: c.inputBg, color: c.text, borderColor: c.border }]}
            value={inputText}
            onChangeText={setInputText}
            placeholder="Message DocChat…"
            placeholderTextColor={c.placeholder}
            multiline
            onSubmitEditing={handleSend}
          />
          <TouchableOpacity
            style={[styles.sendBtn, { backgroundColor: canSend ? c.accent : c.surfaceVariant }]}
            onPress={handleSend}
            disabled={!canSend}
          >
            <Ionicons name="arrow-up" size={20} color={canSend ? '#ffffff' : c.textFaint} />
          </TouchableOpacity>
        </View>

        <ActionSheet
          visible={showAttachSheet}
          title="Attach file"
          onCancel={() => setShowAttachSheet(false)}
          actions={[
            { label: 'Camera', icon: 'camera-outline', onPress: attachFromCamera },
            { label: 'Photo Library', icon: 'image-outline', onPress: attachFromLibrary },
            { label: 'Browse Files', icon: 'folder-open-outline', onPress: attachDocument },
          ]}
        />

      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

function makeStyles(c: ThemeColors) {
  return StyleSheet.create({
    chatArea: { flex: 1 },

    emptyState: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      paddingHorizontal: 32,
      paddingBottom: 60,
    },
    emptyIcon: {
      width: 72,
      height: 72,
      borderRadius: 20,
      justifyContent: 'center',
      alignItems: 'center',
      marginBottom: 20,
    },
    emptyTitle: {
      fontSize: 24,
      fontWeight: '700',
      letterSpacing: -0.5,
      marginBottom: 10,
      textAlign: 'center',
    },
    emptySubtitle: {
      fontSize: 15,
      textAlign: 'center',
      lineHeight: 22,
    },

    userRow: { flexDirection: 'row', justifyContent: 'flex-end', marginBottom: 12 },
    aiRow: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 12, gap: 8 },
    aiAvatar: {
      width: 26,
      height: 26,
      borderRadius: 8,
      justifyContent: 'center',
      alignItems: 'center',
      marginTop: 4,
      flexShrink: 0,
    },

    bubble: { padding: 14, borderRadius: 18 },
    userBubble: {
      backgroundColor: c.userBubble,
      borderBottomRightRadius: 4,
      maxWidth: '85%',
    },
    aiBubble: {
      backgroundColor: c.aiBubble,
      borderBottomLeftRadius: 4,
      borderLeftWidth: 3,
      borderLeftColor: c.accent,
      flex: 1,
    },

    userText: { color: '#ffffff', fontSize: 16, lineHeight: 22 },

    toolBadge: {
      flexDirection: 'row',
      alignItems: 'center',
      marginTop: 10,
      paddingVertical: 5,
      paddingHorizontal: 10,
      borderRadius: 20,
      alignSelf: 'flex-start',
      gap: 6,
    },
    toolDot: { width: 6, height: 6, borderRadius: 3 },
    toolBadgeText: { fontSize: 11, fontWeight: '600' },

    loadingBubble: { flexDirection: 'row', alignItems: 'center', gap: 10 },
    loadingToolText: { fontSize: 12, flexShrink: 1 },

    inputArea: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: 12,
      paddingVertical: 10,
      borderTopWidth: StyleSheet.hairlineWidth,
      gap: 8,
    },
    attachBtn: {
      width: 38,
      height: 38,
      borderRadius: 12,
      justifyContent: 'center',
      alignItems: 'center',
    },
    input: {
      flex: 1,
      borderRadius: 16,
      paddingHorizontal: 16,
      paddingVertical: 10,
      fontSize: 16,
      maxHeight: 120,
      borderWidth: 1,
    },
    sendBtn: {
      width: 38,
      height: 38,
      borderRadius: 12,
      justifyContent: 'center',
      alignItems: 'center',
    },
  });
}

function makeMdStyles(c: ThemeColors) {
  return {
    body: { color: c.aiBubbleText, fontSize: 16, lineHeight: 24 },
    strong: { fontWeight: 'bold' as const },
    em: { fontStyle: 'italic' as const },
    bullet_list: { marginTop: 4, marginBottom: 4 },
    list_item: { marginVertical: 2 },
    code_inline: {
      backgroundColor: c.surfaceVariant,
      borderRadius: 4,
      paddingHorizontal: 5,
      fontFamily: 'monospace',
      color: c.accent,
    },
    fence: {
      backgroundColor: c.surfaceVariant,
      borderRadius: 8,
      padding: 12,
      color: c.text,
    },
  };
}
