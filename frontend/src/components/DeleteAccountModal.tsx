import React, { useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform, StyleSheet, Text, View } from 'react-native';
import { colors, radius, space } from '../lib/theme';
import { Button, Field, InlineError } from './ui';

interface Props {
  visible: boolean;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: (password: string) => void;
}

export function DeleteAccountModal({ visible, loading, error, onClose, onConfirm }: Props) {
  const [password, setPassword] = useState('');

  const [wasVisible, setWasVisible] = useState(visible);
  if (visible !== wasVisible) {
    setWasVisible(visible);
    if (visible) setPassword('');
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.overlay}>
        <View style={styles.sheet} accessibilityViewIsModal>
          <Text accessibilityRole="header" style={styles.title}>Delete your account</Text>
          <Text style={styles.body}>
            This permanently deletes your account and every trip, itinerary, expense and chat you have — there is no undo.
            See the privacy note for details.
          </Text>
          <Field
            testID="delete-account-password"
            label="Confirm your password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoCapitalize="none"
            editable={!loading}
            onSubmitEditing={() => password && onConfirm(password)}
          />
          {error ? <InlineError message={error} /> : null}
          <View style={styles.actions}>
            <Button label="Cancel" variant="ghost" onPress={onClose} disabled={loading} />
            <Button
              testID="delete-account-confirm"
              label="Delete my account"
              variant="danger"
              icon="trash"
              loading={loading}
              disabled={!password}
              onPress={() => onConfirm(password)}
            />
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', padding: space.lg },
  sheet: { backgroundColor: colors.card, borderRadius: radius.lg, padding: space.lg, gap: space.md, maxWidth: 480, width: '100%', alignSelf: 'center' },
  title: { fontSize: 20, fontWeight: '800', color: colors.text },
  body: { fontSize: 14, color: colors.muted, lineHeight: 20 },
  actions: { flexDirection: 'row', justifyContent: 'flex-end', gap: space.sm },
});
