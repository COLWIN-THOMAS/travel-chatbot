import React, { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { colors, radius, space } from '../lib/theme';
import type { ChatMessage } from '../lib/types';

export function ChatBubble({ message }: { message: ChatMessage }) {
  const mine = message.role === 'user';
  return (
    <View style={[styles.row, mine ? styles.rowMine : styles.rowTheirs]}>
      <View
        accessibilityLabel={`${mine ? 'You' : 'Assistant'}: ${message.content}`}
        style={[styles.bubble, mine ? styles.mine : styles.theirs, message.pending && { opacity: 0.6 }]}
      >
        <Text selectable style={[styles.text, mine && { color: '#fff' }]}>{message.content}</Text>
      </View>
    </View>
  );
}

/** Shows progress text that changes if the wait drags on (plan generation can take a minute). */
export function TypingBubble({ building }: { building: boolean }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 8000);
    return () => clearTimeout(t);
  }, []);
  const text = building
    ? slow ? 'Still building your plan – this can take up to a minute…' : 'Building your plan…'
    : slow ? 'Still thinking…' : '';
  return (
    <View style={[styles.row, styles.rowTheirs]} accessibilityLiveRegion="polite" accessibilityLabel="Assistant is typing">
      <View style={[styles.bubble, styles.theirs, styles.typing]}>
        <ActivityIndicator size="small" color={colors.primary} />
        {text ? <Text style={[styles.text, { color: colors.muted }]}>{text}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { paddingHorizontal: space.md, marginVertical: 4, flexDirection: 'row' },
  rowMine: { justifyContent: 'flex-end' },
  rowTheirs: { justifyContent: 'flex-start' },
  bubble: { maxWidth: '85%', paddingHorizontal: space.md, paddingVertical: 10, borderRadius: radius.lg },
  mine: { backgroundColor: colors.userBubble, borderBottomRightRadius: 4 },
  theirs: { backgroundColor: colors.botBubble, borderBottomLeftRadius: 4, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  text: { fontSize: 15, lineHeight: 21, color: colors.text },
  typing: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
});
