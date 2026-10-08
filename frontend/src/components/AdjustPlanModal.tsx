import React, { useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform, StyleSheet, Text, TextInput, View } from 'react-native';
import { colors, radius, space } from '../lib/theme';
import { Button, InlineError } from './ui';

interface Props {
  visible: boolean;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (instructions: string) => void;
}

export function AdjustPlanModal({ visible, loading, error, onClose, onSubmit }: Props) {
  const [text, setText] = useState('');
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.overlay}>
        <View style={styles.sheet} accessibilityViewIsModal>
          <Text accessibilityRole="header" style={styles.title}>Adjust your plan</Text>
          <Text style={styles.body}>
            Describe what to change, or leave blank for a fresh take. Days that have already started (places you&apos;ve ticked, or dates that have passed) stay exactly as they are; only the days after them are rebuilt.
          </Text>
          <TextInput
            testID="adjust-input"
            accessibilityLabel="What should change"
            value={text}
            onChangeText={setText}
            placeholder="e.g. cheaper stays, more street food, fewer museums"
            placeholderTextColor={colors.muted}
            multiline
            maxLength={500}
            editable={!loading}
            style={styles.input}
          />
          {error ? <InlineError message={error} /> : null}
          {loading ? <Text style={styles.body}>Building a new plan – this can take up to a minute…</Text> : null}
          <View style={styles.actions}>
            <Button label="Cancel" variant="ghost" onPress={onClose} disabled={loading} />
            <Button testID="adjust-submit" label="Rebuild plan" icon="refresh" loading={loading} onPress={() => onSubmit(text.trim())} />
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', padding: space.lg },
  sheet: { backgroundColor: colors.card, borderRadius: radius.lg, padding: space.lg, gap: space.md, maxWidth: 520, width: '100%', alignSelf: 'center' },
  title: { fontSize: 20, fontWeight: '800', color: colors.text },
  body: { fontSize: 14, color: colors.muted, lineHeight: 20 },
  input: {
    minHeight: 90, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: space.md,
    fontSize: 16, color: colors.text, textAlignVertical: 'top',
  },
  actions: { flexDirection: 'row', justifyContent: 'flex-end', gap: space.sm },
});
