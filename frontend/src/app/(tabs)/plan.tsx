import { Ionicons } from '@expo/vector-icons';
import React, { useMemo, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { AdjustPlanModal } from '../../components/AdjustPlanModal';
import { ChecklistItem } from '../../components/ChecklistItem';
import { DatePicker } from '../../components/DatePicker';
import { NoTrip } from '../../components/NoTrip';
import { WeatherWidget } from '../../components/WeatherWidget';
import { Badge, Button, Card, Chip, SectionTitle, StateView } from '../../components/ui';
import { addDays, formatRange, formatShort, todayISO } from '../../lib/dates';
import { phaseLabel } from '../../lib/history';
import { inr } from '../../lib/format';
import {
  useActiveTrip, useHotelSearchLink, useItinerary, useRegenerate, useSetTripDates, useToggleVisited,
  useTrainSearchLink, useWeather,
} from '../../lib/hooks';
import { openDeepLink } from '../../lib/openLink';
import { colors, space } from '../../lib/theme';

export default function PlanScreen() {
  const { trip, isLoading, error, refetch } = useActiveTrip();
  const itinerary = useItinerary(trip?.id);
  const weather = useWeather(trip?.id);
  const toggle = useToggleVisited(trip?.id ?? '');
  const regenerate = useRegenerate(trip?.id ?? '');
  const setDates = useSetTripDates(trip?.id ?? '');
  const hotelLink = useHotelSearchLink(trip?.id);
  const trainLink = useTrainSearchLink(trip?.id);
  const [pickingDates, setPickingDates] = useState(false);
  const [selected, setSelected] = useState(1);
  const [adjusting, setAdjusting] = useState(false);

  const days = useMemo(() => itinerary.data?.days ?? [], [itinerary.data]);
  const day = useMemo(() => days.find((d) => d.day_number === selected) ?? days[0], [days, selected]);
  const forecast = weather.data?.days.find((f) => f.day_number === (day?.day_number ?? 1));

  // Open an ongoing trip on today's day instead of Day 1 — done during render (adjusting state when a
  // prop changes, React's documented alternative to an effect), keyed so it only fires once per load.
  const [autoSelectedFor, setAutoSelectedFor] = useState<string | null>(null);
  const autoSelectKey = trip && trip.phase === 'ongoing' && days.length > 0 ? `${trip.id}:${days.length}` : null;
  if (autoSelectKey && autoSelectKey !== autoSelectedFor) {
    setAutoSelectedFor(autoSelectKey);
    const today = days.find((d) => d.date === todayISO());
    if (today) setSelected(today.day_number);
  }

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
          <View style={styles.dateRow}>
            <Ionicons name="calendar-outline" size={16} color={colors.muted} />
            <Text testID="trip-dates" style={[styles.meta, { flex: 1 }]}>
              {trip.start_date ? formatRange(trip.start_date, trip.end_date) : 'Dates not set'}
            </Text>
            <Badge label={phaseLabel(trip.phase)} tone={trip.phase === 'completed' ? 'muted' : trip.phase === 'undated' ? 'warn' : 'success'} />
          </View>
          <Button
            testID="edit-dates"
            label={trip.start_date ? 'Change dates' : 'Set dates'}
            variant="ghost"
            icon="calendar"
            onPress={() => { setDates.reset(); setPickingDates(true); }}
            style={{ alignSelf: 'flex-start', minHeight: 36, paddingHorizontal: 0 }}
          />
          <Text style={styles.meta}>
            {trip.days_count} day{trip.days_count === 1 ? '' : 's'} {'\u2022'} budget {inr(trip.budget_total)}
            {trip.preferences?.length ? ` \u2022 ${trip.preferences.join(', ')}` : ''}
          </Text>
          <Text style={[styles.meta, { color: overBudget ? colors.danger : colors.success, fontWeight: '700', marginTop: 4 }]}>
            Planned {inr(plannedTotal)} of {inr(trip.budget_total)}
          </Text>
          <View style={styles.bookingRow}>
            <Button
              testID="search-hotels"
              label="Search hotels"
              variant="secondary"
              icon="bed-outline"
              loading={hotelLink.isLoading}
              disabled={!hotelLink.data}
              onPress={() => hotelLink.data && openDeepLink(hotelLink.data)}
              style={{ flex: 1 }}
            />
            <Button
              testID="search-trains"
              label="Trains"
              variant="ghost"
              icon="train-outline"
              onPress={() => trainLink.data && openDeepLink(trainLink.data)}
            />
          </View>
        </Card>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
          {days.map((d) => {
            const f = weather.data?.days.find((x) => x.day_number === d.day_number);
            return (
              <Chip
                key={d.id}
                testID={`day-${d.day_number}`}
                label={`Day ${d.day_number}${d.date ?? f?.date ? ` \u2022 ${formatShort(d.date ?? f?.date)}` : ''}`}
                selected={d.day_number === day?.day_number}
                onPress={() => setSelected(d.day_number)}
              />
            );
          })}
        </ScrollView>

        {forecast ? (
          <WeatherWidget forecast={forecast} destination={weather.data?.destination} />
        ) : weather.data?.note ? (
          <Card style={styles.weatherMissing}>
            <Ionicons name="partly-sunny-outline" size={20} color={colors.muted} />
            <Text style={[styles.meta, { flex: 1 }]}>{weather.data.note}</Text>
          </Card>
        ) : weather.error ? (
          <Card style={styles.weatherMissing}>
            <Ionicons name="partly-sunny-outline" size={20} color={colors.muted} />
            <Text style={styles.meta}>Weather is unavailable right now.</Text>
            <Button label="Retry" variant="ghost" onPress={() => weather.refetch()} />
          </Card>
        ) : null}

        {day ? (
          <>
            <SectionTitle right={<Text style={styles.meta}>Day total {inr(day.estimated_total)}</Text>}>
              {`Day ${day.day_number}${day.date ? ` \u2022 ${formatShort(day.date)}` : ''}${day.date === todayISO() ? ' (today)' : ''}`}
            </SectionTitle>
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

      <DatePicker
        visible={pickingDates}
        title={trip.start_date ? 'Change your trip dates' : 'When does your trip start?'}
        value={trip.start_date}
        daysCount={trip.days_count}
        minDate={trip.phase === 'upcoming' || trip.phase === 'undated' ? undefined : addDays(todayISO(), -365)}
        confirmLabel="Save dates"
        skipLabel={trip.start_date ? 'Remove dates' : undefined}
        busy={setDates.isPending}
        error={setDates.error ? setDates.error.message : null}
        onSkip={() => setDates.mutate(null, { onSuccess: () => setPickingDates(false) })}
        onClose={() => setPickingDates(false)}
        onConfirm={(iso) => setDates.mutate(iso, { onSuccess: () => setPickingDates(false) })}
      />

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
  dateRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, marginTop: 2, marginBottom: 2 },
  bookingRow: { flexDirection: 'row', gap: space.sm, alignItems: 'center', marginTop: space.sm },
  meta: { fontSize: 13, color: colors.muted },
  note: { fontSize: 12, color: colors.muted, fontStyle: 'italic', marginLeft: 40, marginBottom: space.sm },
  divider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  weatherMissing: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
});
