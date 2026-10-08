import { Ionicons } from '@expo/vector-icons';
import React, { useMemo, useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import {
  addDays, formatLong, formatRange, monthGrid, monthTitle, parseISO, shiftMonth, toISO, todayISO, WEEKDAY_HEADERS,
} from '../lib/dates';
import { colors, radius, space } from '../lib/theme';
import { Button, InlineError } from './ui';

interface Props {
  visible: boolean;
  title?: string;
  /** Currently chosen start date (YYYY-MM-DD), if any. */
  value?: string | null;
  /** Trip length: the days from the chosen start are shaded so you can see the whole trip on the calendar. */
  daysCount?: number;
  /** Earliest selectable day (default today). */
  minDate?: string;
  /** Latest selectable day (default two years from today). */
  maxDate?: string;
  confirmLabel?: string;
  /** Optional extra choice, e.g. "I haven't decided yet" while planning. */
  skipLabel?: string;
  onSkip?: () => void;
  busy?: boolean;
  error?: string | null;
  onConfirm: (startISO: string) => void;
  onClose: () => void;
}

/** A self-contained month calendar (pure JS, so it works on iOS, Android and web without a native module). */
export function DatePicker({
  visible, title = 'When does your trip start?', value, daysCount = 1, minDate, maxDate, confirmLabel = 'Confirm dates',
  skipLabel, onSkip, busy, error, onConfirm, onClose,
}: Props) {
  const today = todayISO();
  const min = minDate ?? today;
  const max = maxDate ?? addDays(today, 730);
  const [picked, setPicked] = useState<string | null>(value ?? null);
  const initial = parseISO(value) ?? parseISO(min) ?? { y: new Date().getFullYear(), m0: new Date().getMonth(), d: 1 };
  const [view, setView] = useState({ y: initial.y, m0: initial.m0 });

  // Re-seed whenever the picker is (re)opened — done during render (React's documented pattern for
  // "adjusting state when a prop changes"), not an effect, so there's no extra render/flash on open.
  const [wasVisible, setWasVisible] = useState(visible);
  if (visible !== wasVisible) {
    setWasVisible(visible);
    if (visible) {
      setPicked(value ?? null);
      const p = parseISO(value) ?? parseISO(min);
      if (p) setView({ y: p.y, m0: p.m0 });
    }
  }

  const weeks = useMemo(() => monthGrid(view.y, view.m0), [view]);
  const end = picked ? addDays(picked, Math.max(daysCount, 1) - 1) : null;
  const minView = parseISO(min);
  const maxView = parseISO(max);
  const canGoBack = !minView || view.y * 12 + view.m0 > minView.y * 12 + minView.m0;
  const canGoForward = !maxView || view.y * 12 + view.m0 < maxView.y * 12 + maxView.m0;

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.sheet} accessibilityViewIsModal>
          <Text accessibilityRole="header" style={styles.title}>{title}</Text>

          <View style={styles.monthRow}>
            <Pressable
              testID="cal-prev" accessibilityRole="button" accessibilityLabel="Previous month" hitSlop={10}
              disabled={!canGoBack} onPress={() => setView(shiftMonth(view.y, view.m0, -1))}
              style={!canGoBack && { opacity: 0.3 }}
            >
              <Ionicons name="chevron-back" size={24} color={colors.text} />
            </Pressable>
            <Text testID="cal-month" accessibilityLiveRegion="polite" style={styles.month}>{monthTitle(view.y, view.m0)}</Text>
            <Pressable
              testID="cal-next" accessibilityRole="button" accessibilityLabel="Next month" hitSlop={10}
              disabled={!canGoForward} onPress={() => setView(shiftMonth(view.y, view.m0, 1))}
              style={!canGoForward && { opacity: 0.3 }}
            >
              <Ionicons name="chevron-forward" size={24} color={colors.text} />
            </Pressable>
          </View>

          <View style={styles.weekRow}>
            {WEEKDAY_HEADERS.map((h, i) => <Text key={i} style={styles.weekday}>{h}</Text>)}
          </View>

          {weeks.map((week, wi) => (
            <View key={wi} style={styles.weekRow}>
              {week.map((day, di) => {
                if (day === null) return <View key={di} style={styles.cell} />;
                const iso = toISO(view.y, view.m0, day);
                const disabled = iso < min || iso > max;
                const isStart = iso === picked;
                const inTrip = !!picked && !!end && iso > picked && iso <= end;
                return (
                  <Pressable
                    key={di}
                    testID={`cal-day-${iso}`}
                    accessibilityRole="button"
                    accessibilityLabel={formatLong(iso)}
                    accessibilityState={{ disabled, selected: isStart || inTrip }}
                    disabled={disabled}
                    onPress={() => setPicked(iso)}
                    style={[styles.cell, inTrip && styles.inTrip, isStart && styles.start]}
                  >
                    <Text style={[
                      styles.dayText,
                      iso === today && !isStart && { color: colors.primary, fontWeight: '800' },
                      inTrip && { color: colors.primaryDark },
                      isStart && { color: '#fff', fontWeight: '800' },
                      disabled && { color: colors.border },
                    ]}>
                      {day}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          ))}

          <Text testID="cal-summary" style={styles.summary}>
            {picked && end
              ? daysCount > 1
                ? `${formatRange(picked, end)} • ${daysCount} days`
                : formatLong(picked)
              : 'Tap the day you start'}
          </Text>

          {error ? <InlineError message={error} /> : null}

          <View style={styles.actions}>
            {skipLabel && onSkip ? <Button label={skipLabel} variant="ghost" disabled={busy} onPress={onSkip} /> : null}
            <Button label="Cancel" variant="ghost" disabled={busy} onPress={onClose} />
            <Button testID="cal-confirm" label={confirmLabel} icon="calendar" loading={busy} disabled={!picked} onPress={() => picked && onConfirm(picked)} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const CELL = 42;
const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', padding: space.lg },
  sheet: { backgroundColor: colors.card, borderRadius: radius.lg, padding: space.lg, gap: space.sm, maxWidth: 420, width: '100%', alignSelf: 'center' },
  title: { fontSize: 20, fontWeight: '800', color: colors.text },
  monthRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: space.sm },
  month: { fontSize: 16, fontWeight: '700', color: colors.text },
  weekRow: { flexDirection: 'row', justifyContent: 'space-between' },
  weekday: { flex: 1, textAlign: 'center', fontSize: 12, fontWeight: '600', color: colors.muted, paddingVertical: 4 },
  cell: { flex: 1, height: CELL, alignItems: 'center', justifyContent: 'center', borderRadius: 8 },
  inTrip: { backgroundColor: colors.primarySoft, borderRadius: 8 },
  start: { backgroundColor: colors.primary },
  dayText: { fontSize: 15, color: colors.text },
  summary: { textAlign: 'center', fontSize: 14, fontWeight: '600', color: colors.primaryDark, marginTop: space.sm, minHeight: 20 },
  actions: { flexDirection: 'row', justifyContent: 'flex-end', flexWrap: 'wrap', gap: space.sm, marginTop: space.sm },
});
