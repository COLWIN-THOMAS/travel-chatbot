import React, { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { parseAmount } from '../lib/format';
import { colors, radius, space } from '../lib/theme';
import type { ItineraryItem } from '../lib/types';
import { Button, Chip, Field, InlineError } from './ui';

export const EXPENSE_CATEGORIES = ['food', 'transport', 'stay', 'activity', 'shopping', 'other'] as const;

interface Props {
  visible: boolean;
  items: ItineraryItem[];
  presetItemId?: string | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (v: { amount: number; category: string; itemId?: string }) => void;
}

export function ExpenseModal({ visible, items, presetItemId, loading, error, onClose, onSubmit }: Props) {
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState<string>('food');
  const [itemId, setItemId] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (visible) { setAmount(''); setCategory('food'); setItemId(presetItemId ?? null); setTouched(false); }
  }, [visible, presetItemId]);

  const parsed = parseAmount(amount);
  const amountError = touched && parsed === null ? 'Enter an amount greater than 0' : null;

  function submit() {
    setTouched(true);
    if (parsed === null) return;
    onSubmit({ amount: parsed, category, itemId: itemId ?? undefined });
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.overlay}>
        <View style={styles.sheet} accessibilityViewIsModal>
          <Text accessibilityRole="header" style={styles.title}>Log an expense</Text>
          <Field
            testID="expense-amount"
            label="Amount (₹)"
            value={amount}
            onChangeText={setAmount}
            keyboardType="decimal-pad"
            placeholder="0"
            error={amountError}
            autoFocus
            onSubmitEditing={submit}
          />
          <Text style={styles.label}>Category</Text>
          <View style={styles.wrap}>
            {EXPENSE_CATEGORIES.map((c) => (
              <Chip key={c} testID={`cat-${c}`} label={c} selected={category === c} onPress={() => setCategory(c)} />
            ))}
          </View>
          <Text style={styles.label}>For which place? (optional)</Text>
          <ScrollView style={{ maxHeight: 130 }} contentContainerStyle={styles.wrap}>
            <Chip label="None" selected={itemId === null} onPress={() => setItemId(null)} />
            {items.map((i) => (
              <Chip key={i.id} label={i.place_name} selected={itemId === i.id} onPress={() => setItemId(i.id)} />
            ))}
          </ScrollView>
          {error ? <InlineError message={error} /> : null}
          <View style={styles.actions}>
            <Button label="Cancel" variant="ghost" onPress={onClose} disabled={loading} />
            <Button testID="expense-submit" label="Save expense" icon="checkmark" loading={loading} onPress={submit} />
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
  label: { fontSize: 13, fontWeight: '600', color: colors.text },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  actions: { flexDirection: 'row', justifyContent: 'flex-end', gap: space.sm },
});
