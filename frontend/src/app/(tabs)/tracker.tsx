import { Ionicons } from '@expo/vector-icons';
import React, { useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { ChecklistItem } from '../../components/ChecklistItem';
import { ExpenseModal } from '../../components/ExpenseModal';
import { NoTrip } from '../../components/NoTrip';
import { Button, Card, ProgressBar, SectionTitle, StateView } from '../../components/ui';
import { confirmAction } from '../../lib/confirm';
import { formatShort } from '../../lib/dates';
import { budgetTone, inr } from '../../lib/format';
import {
  useActiveTrip, useDeleteExpense, useExpenses, useItinerary, useLogExpense, useToggleVisited, useTracker,
} from '../../lib/hooks';
import { colors, space } from '../../lib/theme';

export default function TrackerScreen() {
  const { trip, isLoading, error, refetch } = useActiveTrip();
  const tripId = trip?.id;
  const summary = useTracker(tripId);
  const itinerary = useItinerary(tripId);
  const expenses = useExpenses(tripId);
  const toggle = useToggleVisited(tripId ?? '');
  const log = useLogExpense(tripId ?? '');
  const del = useDeleteExpense(tripId ?? '');
  const [modal, setModal] = useState<{ open: boolean; itemId: string | null }>({ open: false, itemId: null });

  if (isLoading) return <StateView loading />;
  if (error) return <StateView error={error} onRetry={() => refetch()} />;
  if (!trip) return <NoTrip />;
  if (summary.isLoading || itinerary.isLoading) return <StateView loading />;
  if (summary.error || itinerary.error) {
    return <StateView error={(summary.error ?? itinerary.error) as Error} onRetry={() => { void summary.refetch(); void itinerary.refetch(); }} />;
  }

  const s = summary.data!;
  const days = itinerary.data?.days ?? [];
  const allItems = days.flatMap((d) => d.items);
  const tone = budgetTone(s.percent_used);
  const visitedPct = s.items_total > 0 ? (s.items_visited / s.items_total) * 100 : 0;
  const over = s.remaining < 0;

  return (
    <View style={{ flex: 1 }}>
      <ScrollView
        contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: space.xl * 3 }}
        refreshControl={<RefreshControl refreshing={summary.isRefetching} onRefresh={() => { void summary.refetch(); void itinerary.refetch(); void expenses.refetch(); }} />}
      >
        <Card style={{ gap: space.sm }}>
          <Text style={styles.label}>Spent so far</Text>
          <Text testID="spend-total" style={styles.big}>
            {inr(s.spend_total)} <Text style={styles.of}>of {inr(s.budget_total)}</Text>
          </Text>
          <ProgressBar testID="budget-bar" percent={s.percent_used} tone={tone} label="Budget used" />
          <View style={styles.row}>
            <Text style={[styles.meta, { color: over ? colors.danger : colors.success, fontWeight: '700' }]}>
              {over ? `${inr(-s.remaining)} over budget` : `${inr(s.remaining)} left`}
            </Text>
            <Text style={styles.meta}>{s.percent_used}% used</Text>
          </View>
          {over ? <Text style={styles.alert}>You have gone over your budget – consider trimming the remaining days.</Text> : null}
        </Card>

        <Card style={{ gap: space.sm }}>
          <Text style={styles.label}>Places visited</Text>
          <Text testID="visited-count" style={styles.mid}>{s.items_visited} of {s.items_total}</Text>
          <ProgressBar testID="visited-bar" percent={visitedPct} label="Places visited" />
        </Card>

        {Object.keys(s.spent_by_category).length > 0 ? (
          <View style={styles.cats}>
            {Object.entries(s.spent_by_category).map(([cat, amt]) => (
              <View key={cat} style={styles.catPill}>
                <Text style={styles.catText}>{cat}: {inr(amt)}</Text>
              </View>
            ))}
          </View>
        ) : null}

        <Button testID="add-expense" label="Log an expense" icon="add-circle-outline" onPress={() => setModal({ open: true, itemId: null })} />

        {days.map((d) => (
          <View key={d.id}>
            <SectionTitle right={<Text style={styles.meta}>est {inr(d.estimated_total)} {'\u2022'} spent {inr(d.spend_so_far)}</Text>}>
              Day {d.day_number}{d.date ? ` \u2022 ${formatShort(d.date)}` : ''}
            </SectionTitle>
            <Card>
              {d.items.map((item, i) => (
                <View key={item.id} style={i > 0 ? styles.divider : undefined}>
                  <ChecklistItem
                    item={item}
                    disabled={toggle.isPending}
                    onToggle={(visited) => toggle.mutate({ itemId: item.id, visited })}
                    onAddExpense={() => setModal({ open: true, itemId: item.id })}
                  />
                </View>
              ))}
            </Card>
          </View>
        ))}

        <SectionTitle>Recent expenses</SectionTitle>
        {(expenses.data ?? []).length === 0 ? (
          <Text style={styles.meta}>Nothing logged yet.</Text>
        ) : (
          <Card>
            {(expenses.data ?? []).slice(0, 10).map((e, i) => {
              const place = allItems.find((it) => it.id === e.itinerary_item_id)?.place_name;
              return (
                <View key={e.id} style={[styles.expenseRow, i > 0 && styles.divider]}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.expenseAmount}>{inr(e.amount)}</Text>
                    <Text style={styles.meta}>{[e.category ?? 'other', place].filter(Boolean).join(' \u2022 ')}</Text>
                  </View>
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={`Delete expense of ${inr(e.amount)}`}
                    hitSlop={10}
                    onPress={() => confirmAction('Delete expense?', `${inr(e.amount)} will be removed from your total.`, 'Delete', () => del.mutate(e.id))}
                  >
                    <Ionicons name="trash-outline" size={20} color={colors.danger} />
                  </Pressable>
                </View>
              );
            })}
          </Card>
        )}
      </ScrollView>

      <ExpenseModal
        visible={modal.open}
        items={allItems}
        presetItemId={modal.itemId}
        loading={log.isPending}
        error={log.error ? log.error.message : null}
        onClose={() => { setModal({ open: false, itemId: null }); log.reset(); }}
        onSubmit={(v) => log.mutate(v, { onSuccess: () => setModal({ open: false, itemId: null }) })}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  label: { fontSize: 13, fontWeight: '600', color: colors.muted, textTransform: 'uppercase', letterSpacing: 0.5 },
  big: { fontSize: 30, fontWeight: '800', color: colors.text },
  of: { fontSize: 16, fontWeight: '500', color: colors.muted },
  mid: { fontSize: 20, fontWeight: '700', color: colors.text },
  row: { flexDirection: 'row', justifyContent: 'space-between' },
  meta: { fontSize: 13, color: colors.muted },
  alert: { fontSize: 13, color: colors.danger, backgroundColor: colors.dangerSoft, padding: space.sm, borderRadius: 8 },
  cats: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  catPill: { backgroundColor: colors.primarySoft, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  catText: { fontSize: 12, fontWeight: '600', color: colors.primaryDark },
  divider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  expenseRow: { flexDirection: 'row', alignItems: 'center', gap: space.md, paddingVertical: space.sm },
  expenseAmount: { fontSize: 16, fontWeight: '700', color: colors.text },
});
