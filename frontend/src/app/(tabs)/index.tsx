import { Ionicons } from '@expo/vector-icons';
import { useNavigation, router } from 'expo-router';
import React, { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { ChatBubble, TypingBubble } from '../../components/ChatBubble';
import { HeaderActions } from '../../components/HeaderActions';
import { Button, Chip, InlineError, StateView } from '../../components/ui';
import { useChat } from '../../lib/hooks';
import { useChatSession } from '../../lib/session';
import { colors, radius, space } from '../../lib/theme';
import type { ChatMessage } from '../../lib/types';

const MAX_LEN = 1000;

const GREETING: ChatMessage = {
  role: 'assistant',
  content:
    "Hi! I'm your budget trip planner. Tell me where you'd like to go, your total budget and how many days – for example \"Goa, ₹15,000, 4 days, love food and beaches\". I'll build a day-by-day plan that fits.",
};

const STARTERS = ['Plan a trip to Goa', 'Delhi weekend under ₹8,000', 'Noida, 2 days, ₹5,000', 'Gurugram 3 days, love food'];
const FOLLOW_UPS = ['How much have I spent?', 'Make it cheaper', 'More street food please'];

export default function ChatScreen() {
  const navigation = useNavigation();
  const { newChat } = useChatSession();
  const chat = useChat();
  const [text, setText] = useState('');
  const listRef = useRef<FlatList<ChatMessage>>(null);
  const inputRef = useRef<TextInput>(null);

  useLayoutEffect(() => {
    navigation.setOptions({ headerRight: () => <HeaderActions onNewChat={newChat} /> });
  }, [navigation, newChat]);

  const send = useCallback(async (raw: string) => {
    const message = raw.trim();
    if (!message || chat.sending) return;
    setText('');
    chat.clearSendError();
    try {
      await chat.sendMessage(message);
    } catch {
      setText(message); // put the text back so nothing typed is lost
    }
  }, [chat]);

  if (chat.isLoading) return <StateView loading />;
  if (chat.loadError) return <StateView error={chat.loadError} />;

  const data = chat.messages.length === 0 ? [GREETING] : chat.messages;
  const fresh = chat.messages.length === 0;
  const confirming = chat.state === 'CONFIRM';
  const planReady = chat.state === 'POST_PLAN' && !!chat.tripId;

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
      <FlatList
        ref={listRef}
        testID="chat-list"
        data={data}
        keyExtractor={(_, i) => String(i)}
        renderItem={({ item }) => <ChatBubble message={item} />}
        contentContainerStyle={{ paddingVertical: space.md }}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        ListFooterComponent={
          <View>
            {chat.sending ? <TypingBubble building={confirming} /> : null}
            {chat.sendError ? <InlineError message={chat.sendError.message} /> : null}
          </View>
        }
      />

      <View style={styles.suggestions}>
        {fresh && !chat.sending
          ? STARTERS.map((s) => <Chip key={s} label={s} onPress={() => send(s)} />)
          : null}
        {confirming && !chat.sending ? (
          <>
            <Button testID="confirm-plan" label="Yes, build my plan" icon="checkmark-circle" onPress={() => send('yes')} />
            <Button label="Change something" variant="secondary" onPress={() => inputRef.current?.focus()} />
          </>
        ) : null}
        {planReady && !chat.sending ? (
          <>
            <Button testID="view-plan" label="View my plan" icon="map" onPress={() => router.navigate('/plan')} />
            {FOLLOW_UPS.map((s) => <Chip key={s} label={s} onPress={() => send(s)} />)}
          </>
        ) : null}
      </View>

      <View style={styles.composer}>
        <TextInput
          ref={inputRef}
          testID="chat-input"
          accessibilityLabel="Message"
          value={text}
          onChangeText={setText}
          placeholder={confirming ? 'Type "yes" or what to change…' : 'Type your message…'}
          placeholderTextColor={colors.muted}
          multiline
          maxLength={MAX_LEN}
          editable={!chat.sending}
          style={styles.input}
          onKeyPress={(e) => {
            // Web: Enter sends, Shift+Enter inserts a newline.
            const ne = e.nativeEvent as unknown as { key: string; shiftKey?: boolean };
            if (Platform.OS === 'web' && ne.key === 'Enter' && !ne.shiftKey) {
              (e as unknown as { preventDefault: () => void }).preventDefault();
              void send(text);
            }
          }}
        />
        <Pressable
          testID="send"
          accessibilityRole="button"
          accessibilityLabel="Send message"
          accessibilityState={{ disabled: !text.trim() || chat.sending }}
          disabled={!text.trim() || chat.sending}
          onPress={() => send(text)}
          style={[styles.send, (!text.trim() || chat.sending) && { opacity: 0.4 }]}
        >
          <Ionicons name="send" size={20} color="#fff" />
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  suggestions: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, paddingHorizontal: space.md, paddingBottom: space.sm },
  composer: {
    flexDirection: 'row', alignItems: 'flex-end', gap: space.sm, padding: space.md,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, backgroundColor: colors.card,
  },
  input: {
    flex: 1, minHeight: 44, maxHeight: 120, paddingHorizontal: space.md, paddingTop: 11, paddingBottom: 11,
    backgroundColor: colors.bg, borderRadius: radius.lg, fontSize: 16, color: colors.text,
  },
  send: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
});
