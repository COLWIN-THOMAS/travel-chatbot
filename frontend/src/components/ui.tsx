import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import {
  ActivityIndicator, Pressable, StyleProp, StyleSheet, Text, TextInput, TextInputProps, View, ViewStyle,
} from 'react-native';
import { clampPercent, type BudgetTone } from '../lib/format';
import { colors, radius, space } from '../lib/theme';

export type IconName = React.ComponentProps<typeof Ionicons>['name'];

export function Card({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

interface ButtonProps {
  label: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  loading?: boolean;
  disabled?: boolean;
  icon?: IconName;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

export function Button({ label, onPress, variant = 'primary', loading, disabled, icon, style, testID }: ButtonProps) {
  const inactive = disabled || loading;
  const fg = variant === 'primary' || variant === 'danger' ? '#fff' : variant === 'ghost' ? colors.primary : colors.primaryDark;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!inactive, busy: !!loading }}
      testID={testID}
      onPress={onPress}
      disabled={inactive}
      style={({ pressed }) => [
        styles.button,
        variant === 'primary' && { backgroundColor: colors.primary },
        variant === 'danger' && { backgroundColor: colors.danger },
        variant === 'secondary' && { backgroundColor: colors.primarySoft },
        variant === 'ghost' && { backgroundColor: 'transparent' },
        inactive && { opacity: 0.5 },
        pressed && { opacity: 0.8 },
        style,
      ]}
    >
      {loading ? <ActivityIndicator color={fg} /> : icon ? <Ionicons name={icon} size={18} color={fg} /> : null}
      <Text style={[styles.buttonText, { color: fg }]}>{label}</Text>
    </Pressable>
  );
}

export function Chip({ label, selected, onPress, icon, testID }: {
  label: string; selected?: boolean; onPress?: () => void; icon?: IconName; testID?: string;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: !!selected }}
      testID={testID}
      onPress={onPress}
      style={[styles.chip, selected && { backgroundColor: colors.primary, borderColor: colors.primary }]}
    >
      {icon ? <Ionicons name={icon} size={14} color={selected ? '#fff' : colors.text} /> : null}
      <Text style={[styles.chipText, selected && { color: '#fff' }]}>{label}</Text>
    </Pressable>
  );
}

export function Badge({ label, tone = 'success', icon }: { label: string; tone?: 'success' | 'warn' | 'muted'; icon?: IconName }) {
  const bg = tone === 'success' ? colors.successSoft : tone === 'warn' ? colors.warnSoft : colors.border;
  const fg = tone === 'success' ? colors.success : tone === 'warn' ? colors.warn : colors.muted;
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      {icon ? <Ionicons name={icon} size={12} color={fg} /> : null}
      <Text style={[styles.badgeText, { color: fg }]}>{label}</Text>
    </View>
  );
}

const toneColor: Record<BudgetTone, string> = { ok: colors.success, warn: colors.accent, over: colors.danger };

export function ProgressBar({ percent, tone = 'ok', label, testID }: { percent: number; tone?: BudgetTone; label: string; testID?: string }) {
  const pct = clampPercent(percent);
  return (
    <View
      testID={testID}
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityValue={{ min: 0, max: 100, now: Math.round(pct) }}
      style={styles.track}
    >
      <View style={[styles.fill, { width: `${pct}%`, backgroundColor: toneColor[tone] }]} />
    </View>
  );
}

export function Field({ label, error, style, ...input }: TextInputProps & { label: string; error?: string | null }) {
  return (
    <View style={{ gap: space.xs }}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={colors.muted}
        style={[styles.input, !!error && { borderColor: colors.danger }, style]}
        {...input}
      />
      {error ? <Text style={styles.errorText}>{error}</Text> : null}
    </View>
  );
}

export function SectionTitle({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <View style={styles.sectionRow}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>{children}</Text>
      {right}
    </View>
  );
}

/** One place for the loading / error / empty states every data screen needs. */
export function StateView({ loading, error, onRetry, emptyTitle, emptyBody, action }: {
  loading?: boolean; error?: Error | null; onRetry?: () => void; emptyTitle?: string; emptyBody?: string;
  action?: { label: string; onPress: () => void };
}) {
  if (loading) {
    return (
      <View style={styles.center} accessibilityLiveRegion="polite">
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }
  if (error) {
    return (
      <View style={styles.center} accessibilityLiveRegion="polite">
        <Ionicons name="cloud-offline-outline" size={40} color={colors.muted} />
        <Text style={styles.stateTitle}>Something went wrong</Text>
        <Text style={styles.stateBody}>{error.message}</Text>
        {onRetry ? <Button label="Try again" onPress={onRetry} variant="secondary" /> : null}
      </View>
    );
  }
  return (
    <View style={styles.center}>
      <Ionicons name="sparkles-outline" size={40} color={colors.primary} />
      <Text style={styles.stateTitle}>{emptyTitle}</Text>
      {emptyBody ? <Text style={styles.stateBody}>{emptyBody}</Text> : null}
      {action ? <Button label={action.label} onPress={action.onPress} /> : null}
    </View>
  );
}

export function InlineError({ message }: { message: string }) {
  return (
    <View style={styles.inlineError} accessibilityLiveRegion="polite">
      <Ionicons name="alert-circle" size={16} color={colors.danger} />
      <Text style={styles.inlineErrorText}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card, borderRadius: radius.lg, padding: space.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  button: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space.sm,
    minHeight: 46, paddingHorizontal: space.lg, borderRadius: radius.md,
  },
  buttonText: { fontSize: 15, fontWeight: '600' },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: space.md, minHeight: 36,
    borderRadius: radius.pill, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border,
  },
  chipText: { fontSize: 14, color: colors.text, fontWeight: '500' },
  badge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill, alignSelf: 'flex-start' },
  badgeText: { fontSize: 12, fontWeight: '600' },
  track: { height: 12, borderRadius: radius.pill, backgroundColor: colors.border, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: radius.pill },
  fieldLabel: { fontSize: 13, fontWeight: '600', color: colors.text },
  input: {
    minHeight: 46, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: space.md,
    backgroundColor: colors.card, fontSize: 16, color: colors.text,
  },
  errorText: { color: colors.danger, fontSize: 13 },
  sectionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: space.lg, marginBottom: space.sm },
  sectionTitle: { fontSize: 17, fontWeight: '700', color: colors.text },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.md, padding: space.xl },
  stateTitle: { fontSize: 18, fontWeight: '700', color: colors.text, textAlign: 'center' },
  stateBody: { fontSize: 14, color: colors.muted, textAlign: 'center', maxWidth: 320 },
  inlineError: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: space.sm },
  inlineErrorText: { color: colors.danger, fontSize: 13, flex: 1 },
});
