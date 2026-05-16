// app/index.tsx
import { useState } from 'react';
import { StyleSheet, Text, View, TextInput, TouchableOpacity, ScrollView, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Markdown from 'react-native-markdown-display';
import { sendChatMessage } from '../src/api';

type Message = {
  role: 'user' | 'assistant';
  content: string;
  metadata?: {
    tools_executed: string[];
  };
};

export default function ChatScreen() {
  const [inputText, setInputText] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async () => {
    if (!inputText.trim()) return;

    // 1. Add user message to UI immediately
    const userMessage: Message = { role: 'user', content: inputText };
    const newHistory = [...messages, userMessage];
    setMessages(newHistory);
    setInputText('');
    setIsLoading(true);

    // 2. Send the entire history to your LangChain backend
    const aiResponse = await sendChatMessage(inputText);

    // 3. Add AI response to UI
    setMessages([...newHistory, aiResponse as Message]);
    setIsLoading(false);
  };

  return (
    // 1. KeyboardAvoidingView is now the ABSOLUTE ROOT
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: '#f5f5f5' }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 60 : 0} // Accounts for iOS header/notch
    >
      {/* 2. SafeAreaView goes INSIDE the keyboard view */}
      <SafeAreaView style={{ flex: 1 }} edges={['bottom', 'left', 'right']}>
        
        {/* Chat History Area */}
        <ScrollView 
          style={styles.chatArea} 
          contentContainerStyle={{ padding: 20, flexGrow: 1 }} // flexGrow ensures messages push up
          keyboardShouldPersistTaps="handled" // Lets users tap buttons without dismissing keyboard
        >
          {messages.map((msg, index) => (<View key={index} style={[styles.messageBubble, msg.role === 'user' ? styles.userBubble : styles.aiBubble]}>
            
            {/* If it's the user, render normal text. If it's the AI, render Markdown! */}
            {msg.role === 'user' ? (
              <Text style={styles.userText}>{msg.content}</Text>
            ) : (
              <Markdown style={markdownStyles}>
                {msg.content}
              </Markdown>
            )}
            
            {/* Your awesome Tool Badge stays right here */}
            {msg.metadata && msg.metadata.tools_executed && msg.metadata.tools_executed.length > 0 && (
              <View style={styles.toolBadge}>
                <Text style={styles.toolBadgeText}>
                  ⚙️ Used: {msg.metadata.tools_executed.join(', ')}
                </Text>
              </View>
              )}
            </View>
            ))}

        </ScrollView>

        {/* Input Area */}
        <View style={styles.inputArea}>
          <TextInput
             // ... your existing text input ...
             style={styles.input}
             value={inputText}
             onChangeText={setInputText}
             placeholder="Log a workout..."
          />
          <TouchableOpacity style={styles.sendButton} onPress={handleSend}>
            <Text style={styles.sendButtonText}>Send</Text>
          </TouchableOpacity>
        </View>

      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

// Basic styling that works on both Web and Mobile
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  chatArea: { flex: 1 },
  messageBubble: { padding: 15, borderRadius: 20, marginBottom: 10, maxWidth: '80%' },
  userBubble: { backgroundColor: '#007AFF', alignSelf: 'flex-end', borderBottomRightRadius: 5 },
  aiBubble: { backgroundColor: '#E5E5EA', alignSelf: 'flex-start', borderBottomLeftRadius: 5 },
  userText: { color: 'white', fontSize: 16 },
  aiText: { color: 'black', fontSize: 16 },
  inputArea: { flexDirection: 'row', padding: 15, backgroundColor: 'white', borderTopWidth: 1, borderColor: '#ddd' },
  input: { flex: 1, backgroundColor: '#f0f0f0', borderRadius: 25, paddingHorizontal: 20, fontSize: 16, marginRight: 10, height: 50 },
  sendButton: { backgroundColor: '#007AFF', borderRadius: 25, justifyContent: 'center', paddingHorizontal: 20, height: 50 },
  sendButtonText: { color: 'white', fontSize: 16, fontWeight: 'bold' },
  // Add these to your StyleSheet.create({})
  toolBadge: {
    marginTop: 8,
    backgroundColor: '#D1E8FF', // A nice soft blue
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 12,
    alignSelf: 'flex-start',
  },
  toolBadgeText: {
    fontSize: 12,
    color: '#004A99',
    fontWeight: '600',
  },
});

// Custom styles just for the Markdown parser
const markdownStyles = StyleSheet.create({
  body: {
    color: 'black',
    fontSize: 16,
    lineHeight: 24,
  },
  strong: {
    fontWeight: 'bold',
  },
  em: {
    fontStyle: 'italic',
  },
  bullet_list: {
    marginTop: 5,
    marginBottom: 5,
  },
  list_item: {
    marginVertical: 2,
  },
  code_inline: {
    backgroundColor: '#d1d1d6',
    borderRadius: 4,
    paddingHorizontal: 5,
    fontFamily: 'monospace',
  },
});