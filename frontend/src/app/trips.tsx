import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React, { useMemo, useState } from 'react';
import { Pressable, SectionList, StyleSheet, Text, View } from 'react-native';
import { DeleteAccountModal } from '../components/DeleteAccountModal';
import { Badge, Button, Card, ProgressBar, StateView } from '../components/ui';
import { ApiError } from '../lib/api';
import { useAuth } from '../lib/auth';
import { confirmAction } from '../lib/confirm';
import { formatRange } from '../lib/dates';
import { budgetTone, inr } from '../lib/format';
import { groupTrips, historyTotals, phaseLabel } from '../lib/history';
import { useActiveTrip, useDeleteTrip, useTrips } from '../lib/hooks';
import { useChatSession } from '../lib/session';
import { colors, space } from '../lib/theme';
import type { TripSummary } from '../lib/types';

function TripRow({ trip, current, onOpen, onDelete }: {
  trip: TripSummary; current: boolean; onOpen: () => void; onDelete: () => void;
}) {
  const happened = trip.phase === 'completed' || trip.phase === 'ongoing';
  const percent = trip.budget_total > 0 ? (trip.spend_total / trip.budget_total) * 100 : 0;
  return (
    <Card style={styles.row}>
      <Pressable
        testID={`trip-${trip.id}`}
        accessibilityRole="button"
        accessibilityLabel={`Open trip to ${trip.destination}`}
        onPress={onOpen}
        style={{ flex: 1, gap: 4 }}
      >
        <Text style={styles.title}>{trip.destination}</Text>
        <Text style={styles.dates}>
          {trip.start_date ? formatRange(trip.start_date, trip.end_date) : 'Dates not set'}
        </Text>
        <Text style={styles.meta}>
          {trip.days_count} day{trip.days_count === 1 ? '' : 's'} {'•'} budget {inr(trip.budget_total)}
          {trip.preferences?.length ? ` • ${trip.preferences.join(', ')}` : ''}
        </Text>

        {happened ? (
          <View style={{ gap: 4, marginTop: 4 }}>
            <ProgressBar
              percent={percent}
              tone={budgetTone(percent)}
              label={`Spent ${inr(trip.spend_total)} of ${inr(trip.budget_total)}`}
            />
            <Text style={styles.meta}>
              Spent {inr(trip.spend_total)} of {inr(trip.budget_total)} {'•'} {trip.items_visited}/{trip.items_total} places visited
            </Text>
          </View>
        ) : trip.items_total > 0 ? (
          <Text style={styles.meta}>Planned {inr(trip.estimated_total)} across {trip.items_total} places</Text>
        ) : null}

        <View style={styles.badges}>
          <Badge
            label={phaseLabel(trip.phase)}
            tone={trip.phase === 'completed' ? 'muted' : trip.phase === 'undated' ? 'warn' : 'success'}
            icon={trip.phase === 'completed' ? 'checkmark-done' : trip.phase === 'ongoing' ? 'navigate' : 'calendar-outline'}
          />
          {current ? <Badge label="Open in app" icon="checkmark-circle" /> : null}
        </View>
      </Pressable>
      {/* A sibling, not a child: interactive elements can't be nested (invalid HTML on web). */}
      <Pressable
        testID={`delete-trip-${trip.id}`}
        accessibilityRole="button"
        accessibilityLabel={`Delete trip to ${trip.destination}`}
        hitSlop={10}
        onPress={onDelete}
      >
        <Ionicons name="trash-outline" size={22} color={colors.danger} />
      </Pressable>
    </Card>
  );
}

export default function TripsScreen() {
  const trips = useTrips();
  const { trip: active } = useActiveTrip();
  const { setActiveTripId, newChat } = useChatSession();
  const { user, signOut, deleteAccount } = useAuth();
  const del = useDeleteTrip();
  const [deletingAccount, setDeletingAccount] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const sections = useMemo(() => groupTrips(trips.data ?? []), [trips.data]);
  const totals = useMemo(() => historyTotals(trips.data ?? []), [trips.data]);

  async function confirmDeleteAccount(password: string) {
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await deleteAccount(password);
    } catch (e) {
      setDeleteError(e instanceof ApiError ? e.message : 'Something went wrong. Please try again.');
      setDeleteBusy(false);
    }
  }

  function open(id: string) {
    setActiveTripId(id);
    router.dismissTo('/plan');
  }

  return (
    <View style={{ flex: 1 }}>
      {trips.isLoading || trips.error || (trips.data ?? []).length === 0 ? (
        <StateView
          loading={trips.isLoading}
          error={trips.error}
          onRetry={() => trips.refetch()}
          emptyTitle="No trips yet"
          emptyBody="Chat with the assistant to plan your first trip. Every trip you make is kept here as your travel history."
          action={{ label: 'Start planning', onPress: () => router.dismissTo('/') }}
        />
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(t) => t.id}
          stickySectionHeadersEnabled={false}
          contentContainerStyle={{ padding: space.lg, gap: space.md }}
          ListHeaderComponent={
            <Card style={styles.totals}>
              <View style={styles.stat}>
                <Text style={styles.statValue}>{totals.trips}</Text>
                <Text style={styles.statLabel}>{totals.trips === 1 ? 'trip' : 'trips'}</Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statValue}>{totals.completed}</Text>
                <Text style={styles.statLabel}>completed</Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statValue}>{inr(totals.spent)}</Text>
                <Text style={styles.statLabel}>spent in total</Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statValue}>{totals.placesVisited}</Text>
                <Text style={styles.statLabel}>places visited</Text>
              </View>
            </Card>
          }
          renderSectionHeader={({ section }) => (
            <Text accessibilityRole="header" style={styles.sectionTitle}>
              {section.title} ({section.data.length})
            </Text>
          )}
          ItemSeparatorComponent={() => <View style={{ height: space.md }} />}
          renderItem={({ item }) => (
            <TripRow
              trip={item}
              current={item.id === active?.id}
              onOpen={() => open(item.id)}
              onDelete={() =>
                confirmAction(
                  'Delete trip?',
                  `"${item.destination}" and its itinerary and expenses will be removed from your history for good.`,
                  'Delete',
                  () => del.mutate(item.id),
                )}
            />
          )}
        />
      )}
      <View style={styles.footer}>
        <Button label="Plan a new trip" icon="add-circle-outline" onPress={() => { newChat(); router.dismissTo('/'); }} />
        <Text style={styles.account}>{user?.email}</Text>
        <Button label="Sign out" variant="ghost" onPress={() => { void signOut(); }} />
        <Button
          testID="delete-account"
          label="Delete account"
          variant="ghost"
          icon="trash-outline"
          onPress={() => { setDeleteError(null); setDeletingAccount(true); }}
        />
      </View>

      <DeleteAccountModal
        visible={deletingAccount}
        loading={deleteBusy}
        error={deleteError}
        onClose={() => { if (!deleteBusy) setDeletingAccount(false); }}
        onConfirm={confirmDeleteAccount}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  title: { fontSize: 18, fontWeight: '700', color: colors.text },
  dates: { fontSize: 14, fontWeight: '600', color: colors.primaryDark },
  meta: { fontSize: 13, color: colors.muted },
  badges: { flexDirection: 'row', gap: space.sm, flexWrap: 'wrap', marginTop: 4 },
  sectionTitle: { fontSize: 17, fontWeight: '700', color: colors.text, marginTop: space.md, marginBottom: space.sm },
  totals: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: space.md },
  stat: { alignItems: 'center', flexGrow: 1, minWidth: 70 },
  statValue: { fontSize: 20, fontWeight: '800', color: colors.primaryDark },
  statLabel: { fontSize: 12, color: colors.muted },
  footer: { padding: space.lg, gap: space.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, backgroundColor: colors.card },
  account: { textAlign: 'center', fontSize: 12, color: colors.muted },
});
