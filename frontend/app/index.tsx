import { useMemo, useState } from 'react';
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
import { sendChatMessage } from '../src/api';
import { useTheme, type ThemeColors } from '../src/theme';

type Message = {
  role: 'user' | 'assistant';
  content: string;
  metadata?: { tools_executed: string[] };
};

export default function ChatScreen() {
  const { theme } = useTheme();
  const c = theme.colors;
  const styles = useMemo(() => makeStyles(c), [theme]);
  const mdStyles = useMemo(() => makeMdStyles(c), [theme]);

  const [inputText, setInputText] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async () => {
    if (!inputText.trim()) return;
    const userMessage: Message = { role: 'user', content: inputText };
    const newHistory = [...messages, userMessage];
    setMessages(newHistory);
    setInputText('');
    setIsLoading(true);
    const aiResponse = await sendChatMessage(inputText);
    setMessages([...newHistory, aiResponse as Message]);
    setIsLoading(false);
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: c.background }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 60 : 0}
    >
      <SafeAreaView style={{ flex: 1 }} edges={['bottom', 'left', 'right']}>

        <ScrollView
          style={styles.chatArea}
          contentContainerStyle={{ padding: 16, flexGrow: 1 }}
          keyboardShouldPersistTaps="handled"
        >
          {messages.map((msg, i) => (
            <View
              key={i}
              style={[
                styles.bubble,
                msg.role === 'user' ? styles.userBubble : styles.aiBubble,
              ]}
            >
              {msg.role === 'user' ? (
                <Text style={styles.userText}>{msg.content}</Text>
              ) : (
                <Markdown style={mdStyles}>{msg.content}</Markdown>
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

        <View style={styles.inputArea}>
          <TextInput
            style={styles.input}
            value={inputText}
            onChangeText={setInputText}
            placeholder="Message..."
            placeholderTextColor={c.placeholder}
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
    bubble: {
      padding: 14,
      borderRadius: 20,
      marginBottom: 10,
      maxWidth: '82%',
    },
    userBubble: {
      backgroundColor: c.userBubble,
      alignSelf: 'flex-end',
      borderBottomRightRadius: 4,
    },
    aiBubble: {
      backgroundColor: c.aiBubble,
      alignSelf: 'flex-start',
      borderBottomLeftRadius: 4,
    },
    userText: { color: '#ffffff', fontSize: 16 },
    toolBadge: {
      marginTop: 8,
      backgroundColor: c.drawerActiveBg,
      paddingVertical: 4,
      paddingHorizontal: 8,
      borderRadius: 12,
      alignSelf: 'flex-start',
    },
    toolBadgeText: { fontSize: 12, color: c.accent, fontWeight: '600' },
    inputArea: {
      flexDirection: 'row',
      padding: 12,
      backgroundColor: c.surface,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderColor: c.border,
      gap: 10,
    },
    input: {
      flex: 1,
      backgroundColor: c.inputBg,
      borderRadius: 22,
      paddingHorizontal: 18,
      fontSize: 16,
      height: 46,
      color: c.text,
    },
    sendBtn: {
      backgroundColor: c.accent,
      borderRadius: 22,
      justifyContent: 'center',
      paddingHorizontal: 20,
      height: 46,
    },
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
    code_inline: {
      backgroundColor: c.surfaceVariant,
      borderRadius: 4,
      paddingHorizontal: 5,
      fontFamily: 'monospace',
      color: c.text,
    },
    fence: {
      backgroundColor: c.surfaceVariant,
      borderRadius: 6,
      padding: 10,
      color: c.text,
    },
  };
}
