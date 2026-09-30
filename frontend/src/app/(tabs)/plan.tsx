import { Ionicons } from '@expo/vector-icons';
import React, { useMemo, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { AdjustPlanModal } from '../../components/AdjustPlanModal';
import { ChecklistItem } from '../../components/ChecklistItem';
import { NoTrip } from '../../components/NoTrip';
import { WeatherWidget } from '../../components/WeatherWidget';
import { Button, Card, Chip, SectionTitle, StateView } from '../../components/ui';
import { inr } from '../../lib/format';
import { useActiveTrip, useItinerary, useRegenerate, useToggleVisited, useWeather } from '../../lib/hooks';
import { colors, space } from '../../lib/theme';

function shortDate(iso?: string) {
  if (!iso) return '';
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
}

export default function PlanScreen() {
  const { trip, isLoading, error, refetch } = useActiveTrip();
  const itinerary = useItinerary(trip?.id);
  const weather = useWeather(trip?.id);
  const toggle = useToggleVisited(trip?.id ?? '');
  const regenerate = useRegenerate(trip?.id ?? '');
  const [selected, setSelected] = useState(1);
  const [adjusting, setAdjusting] = useState(false);

  const days = itinerary.data?.days ?? [];
  const day = useMemo(() => days.find((d) => d.day_number === selected) ?? days[0], [days, selected]);
  const forecast = weather.data?.days.find((f) => f.day_number === (day?.day_number ?? 1));
  const plannedTotal = days.reduce((sum, d) => sum + d.estimated_total, 0);

  if (isLoading) return <StateView loading />;
  if (error) return <StateView error={error} onRetry={() => refetch()} />;
  if (!trip) return <NoTrip />;
  if (itinerary.isLoading) return <StateView loading />;
  if (itinerary.error) return <StateView error={itinerary.error} onRetry={() => itinerary.refetch()} />;
  if (days.length === 0) {
    return <StateView emptyTitle="No itinerary yet" emptyBody="This trip has no plan. Ask the assistant to build one." />;
  }

  const overBudget = plannedTotal > trip.budget_total;

  return (
    <View style={{ flex: 1 }}>
      <ScrollView
        contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: space.xl * 2 }}
        refreshControl={<RefreshControl refreshing={itinerary.isRefetching} onRefresh={() => { void itinerary.refetch(); void weather.refetch(); }} />}
      >
        <Card>
          <Text style={styles.dest}>{trip.destination}</Text>
          <Text style={styles.meta}>
            {trip.days_count} day{trip.days_count === 1 ? '' : 's'} {'\u2022'} budget {inr(trip.budget_total)}
            {trip.preferences?.length ? ` \u2022 ${trip.preferences.join(', ')}` : ''}
          </Text>
          <Text style={[styles.meta, { color: overBudget ? colors.danger : colors.success, fontWeight: '700', marginTop: 4 }]}>
            Planned {inr(plannedTotal)} of {inr(trip.budget_total)}
          </Text>
        </Card>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
          {days.map((d) => {
            const f = weather.data?.days.find((x) => x.day_number === d.day_number);
            return (
              <Chip
                key={d.id}
                testID={`day-${d.day_number}`}
                label={`Day ${d.day_number}${f ? ` \u2022 ${shortDate(f.date)}` : ''}`}
                selected={d.day_number === day?.day_number}
                onPress={() => setSelected(d.day_number)}
              />
            );
          })}
        </ScrollView>

        {forecast ? (
          <WeatherWidget forecast={forecast} destination={weather.data?.destination} />
        ) : weather.error ? (
          <Card style={styles.weatherMissing}>
            <Ionicons name="partly-sunny-outline" size={20} color={colors.muted} />
            <Text style={styles.meta}>Weather is unavailable right now.</Text>
            <Button label="Retry" variant="ghost" onPress={() => weather.refetch()} />
          </Card>
        ) : null}

        {day ? (
          <>
            <SectionTitle right={<Text style={styles.meta}>Day total {inr(day.estimated_total)}</Text>}>Day {day.day_number}</SectionTitle>
            <Card>
              {day.items.map((item, i) => (
                <View key={item.id} style={i > 0 ? styles.divider : undefined}>
                  <ChecklistItem item={item} disabled={toggle.isPending} onToggle={(visited) => toggle.mutate({ itemId: item.id, visited })} />
                  {item.notes ? <Text style={styles.note}>{item.notes}</Text> : null}
                </View>
              ))}
            </Card>
          </>
        ) : null}

        <Button testID="adjust-plan" label="Adjust plan" variant="secondary" icon="options-outline" onPress={() => setAdjusting(true)} />
      </ScrollView>

      <AdjustPlanModal
        visible={adjusting}
        loading={regenerate.isPending}
        error={regenerate.error ? regenerate.error.message : null}
        onClose={() => { setAdjusting(false); regenerate.reset(); }}
        onSubmit={(instructions) => regenerate.mutate(instructions, { onSuccess: () => { setAdjusting(false); setSelected(1); } })}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  dest: { fontSize: 24, fontWeight: '800', color: colors.text },
  meta: { fontSize: 13, color: colors.muted },
  note: { fontSize: 12, color: colors.muted, fontStyle: 'italic', marginLeft: 40, marginBottom: space.sm },
  divider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  weatherMissing: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
});
