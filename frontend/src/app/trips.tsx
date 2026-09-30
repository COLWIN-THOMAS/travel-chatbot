import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { Badge, Button, Card, StateView } from '../components/ui';
import { confirmAction } from '../lib/confirm';
import { inr } from '../lib/format';
import { useActiveTrip, useDeleteTrip, useTrips } from '../lib/hooks';
import { useAuth } from '../lib/auth';
import { useChatSession } from '../lib/session';
import { colors, space } from '../lib/theme';

export default function TripsScreen() {
  const trips = useTrips();
  const { trip: active } = useActiveTrip();
  const { setActiveTripId, newChat } = useChatSession();
  const { user, signOut } = useAuth();
  const del = useDeleteTrip();

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
          emptyBody="Chat with the assistant to plan your first trip."
          action={{ label: 'Start planning', onPress: () => router.dismissTo('/') }}
        />
      ) : (
        <FlatList
          data={trips.data}
          keyExtractor={(t) => t.id}
          contentContainerStyle={{ padding: space.lg, gap: space.md }}
          renderItem={({ item }) => (
            <Card style={styles.row}>
              <Pressable
                testID={`trip-${item.id}`}
                accessibilityRole="button"
                accessibilityLabel={`Open trip to ${item.destination}`}
                onPress={() => open(item.id)}
                style={{ flex: 1, gap: 4 }}
              >
                <Text style={styles.title}>{item.destination}</Text>
                <Text style={styles.meta}>
                  {item.days_count} day{item.days_count === 1 ? '' : 's'} {'\u2022'} {inr(item.budget_total)}
                  {item.preferences?.length ? ` \u2022 ${item.preferences.join(', ')}` : ''}
                </Text>
                {item.id === active?.id ? <Badge label="Current trip" icon="checkmark-circle" /> : null}
              </Pressable>
              {/* A sibling, not a child: interactive elements can't be nested (invalid HTML on web). */}
              <Pressable
                testID={`delete-trip-${item.id}`}
                accessibilityRole="button"
                accessibilityLabel={`Delete trip to ${item.destination}`}
                hitSlop={10}
                onPress={() =>
                  confirmAction('Delete trip?', `"${item.destination}" and its itinerary and expenses will be removed.`, 'Delete', () =>
                    del.mutate(item.id))
                }
              >
                <Ionicons name="trash-outline" size={22} color={colors.danger} />
              </Pressable>
            </Card>
          )}
        />
      )}
      <View style={styles.footer}>
        <Button label="Plan a new trip" icon="add-circle-outline" onPress={() => { newChat(); router.dismissTo('/'); }} />
        <Text style={styles.account}>{user?.email}</Text>
        <Button label="Sign out" variant="ghost" onPress={() => { void signOut(); }} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  title: { fontSize: 18, fontWeight: '700', color: colors.text },
  meta: { fontSize: 13, color: colors.muted },
  footer: { padding: space.lg, gap: space.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, backgroundColor: colors.card },
  account: { textAlign: 'center', fontSize: 12, color: colors.muted },
});
