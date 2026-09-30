import { Ionicons } from '@expo/vector-icons';
import React, { useMemo, useState } from 'react';
import { FlatList, Pressable, StyleSheet, View } from 'react-native';
import { NoTrip } from '../../components/NoTrip';
import { HotelCard, PlaceRow } from '../../components/PlaceCards';
import { Chip, StateView } from '../../components/ui';
import { isBudgetFriendly } from '../../lib/format';
import { useActiveTrip, usePlaces } from '../../lib/hooks';
import { colors, space } from '../../lib/theme';
import type { PlaceCategory } from '../../lib/types';

const TABS: { key: PlaceCategory; label: string; icon: React.ComponentProps<typeof Ionicons>['name'] }[] = [
  { key: 'hotel', label: 'Hotels', icon: 'bed-outline' },
  { key: 'restaurant', label: 'Restaurants', icon: 'restaurant-outline' },
  { key: 'attraction', label: 'Things to do', icon: 'camera-outline' },
];

export default function ExploreScreen() {
  const { trip, isLoading, error, refetch } = useActiveTrip();
  const [category, setCategory] = useState<PlaceCategory>('hotel');
  const [grid, setGrid] = useState(false);
  const [budgetOnly, setBudgetOnly] = useState(false);
  const [topRated, setTopRated] = useState(false);
  const places = usePlaces(trip?.id, category);

  const shown = useMemo(() => {
    let list = places.data ?? [];
    if (budgetOnly) list = list.filter((p) => isBudgetFriendly(p.price_level));
    if (topRated) list = [...list].sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0));
    return list;
  }, [places.data, budgetOnly, topRated]);

  if (isLoading) return <StateView loading />;
  if (error) return <StateView error={error} onRetry={() => refetch()} />;
  if (!trip) return <NoTrip />;

  const useGrid = grid && category !== 'hotel';

  return (
    <View style={{ flex: 1 }}>
      <View style={styles.controls}>
        <View style={styles.row}>
          {TABS.map((t) => (
            <Chip key={t.key} testID={`tab-${t.key}`} icon={t.icon} label={t.label} selected={category === t.key} onPress={() => setCategory(t.key)} />
          ))}
        </View>
        <View style={[styles.row, { justifyContent: 'space-between' }]}>
          <View style={styles.row}>
            <Chip testID="filter-budget" label="Budget-friendly" selected={budgetOnly} onPress={() => setBudgetOnly((v) => !v)} />
            <Chip testID="filter-top" label="Top rated" selected={topRated} onPress={() => setTopRated((v) => !v)} />
          </View>
          {category !== 'hotel' ? (
            <Pressable
              testID="toggle-grid"
              accessibilityRole="button"
              accessibilityLabel={grid ? 'Switch to list view' : 'Switch to grid view'}
              hitSlop={8}
              onPress={() => setGrid((g) => !g)}
            >
              <Ionicons name={grid ? 'list' : 'grid'} size={22} color={colors.primaryDark} />
            </Pressable>
          ) : null}
        </View>
      </View>

      {places.isLoading || places.error || shown.length === 0 ? (
        <StateView
          loading={places.isLoading}
          error={places.error}
          onRetry={() => places.refetch()}
          emptyTitle={budgetOnly ? 'Nothing matches that filter' : 'No places found'}
          emptyBody={budgetOnly ? 'Google only lists a price tier for some places. Try turning off "Budget-friendly".' : `We couldn't find any near ${trip.destination}.`}
        />
      ) : (
        <FlatList
          key={useGrid ? 'grid' : 'list'}
          testID="places-list"
          data={shown}
          numColumns={useGrid ? 2 : 1}
          columnWrapperStyle={useGrid ? { gap: space.md } : undefined}
          keyExtractor={(p) => p.id}
          contentContainerStyle={{ padding: space.lg, gap: space.md }}
          renderItem={({ item }) => (category === 'hotel' ? <HotelCard place={item} /> : <PlaceRow place={item} grid={useGrid} />)}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  controls: { padding: space.lg, paddingBottom: space.sm, gap: space.sm, backgroundColor: colors.card, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, alignItems: 'center' },
});
