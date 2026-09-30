import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { isBudgetFriendly, priceTier } from '../lib/format';
import { categoryMeta, colors, radius, space } from '../lib/theme';
import type { PlaceSummary } from '../lib/types';
import { Badge } from './ui';

function open(place: PlaceSummary) {
  router.push({ pathname: '/place/[id]', params: { id: place.id, name: place.name } });
}

function Rating({ value }: { value: number | null }) {
  if (value == null) return <Text style={styles.muted}>No rating</Text>;
  return (
    <View style={styles.inline}>
      <Ionicons name="star" size={14} color={colors.accent} />
      <Text style={styles.ratingText}>{value.toFixed(1)}</Text>
    </View>
  );
}

const icon = (c: PlaceSummary['category']) => categoryMeta[c].icon as React.ComponentProps<typeof Ionicons>['name'];

/** Wide hotel card (see docs/wireframes/hotel-card). Google's list call carries no photo, so the image slot is an icon tile. */
export function HotelCard({ place }: { place: PlaceSummary }) {
  return (
    <Pressable
      testID={`place-${place.id}`}
      accessibilityRole="button"
      accessibilityLabel={`${place.name}, ${priceTier(place.price_level)}, rated ${place.rating ?? 'unrated'}`}
      onPress={() => open(place)}
      style={({ pressed }) => [styles.hotel, pressed && { opacity: 0.85 }]}
    >
      <View style={styles.hotelImage}>
        <Ionicons name={icon(place.category)} size={40} color={colors.primary} />
      </View>
      <View style={{ padding: space.md, gap: 6 }}>
        <Text style={styles.name} numberOfLines={2}>{place.name}</Text>
        {place.address ? <Text style={styles.muted} numberOfLines={1}>{place.address}</Text> : null}
        <View style={[styles.inline, { justifyContent: 'space-between' }]}>
          <View style={styles.inline}>
            <Text style={styles.tier}>{priceTier(place.price_level)}</Text>
            <Rating value={place.rating} />
          </View>
          {isBudgetFriendly(place.price_level) ? <Badge label="Budget-friendly" icon="pricetag" /> : null}
        </View>
      </View>
    </Pressable>
  );
}

/** Compact row (list mode) or tile (grid mode) for restaurants and attractions. */
export function PlaceRow({ place, grid }: { place: PlaceSummary; grid?: boolean }) {
  return (
    <Pressable
      testID={`place-${place.id}`}
      accessibilityRole="button"
      accessibilityLabel={`${place.name}, ${priceTier(place.price_level)}, rated ${place.rating ?? 'unrated'}`}
      onPress={() => open(place)}
      style={({ pressed }) => [grid ? styles.tile : styles.row, pressed && { opacity: 0.85 }]}
    >
      <View style={[styles.thumb, grid && { width: '100%', height: 90 }]}>
        <Ionicons name={icon(place.category)} size={28} color={colors.primary} />
      </View>
      <View style={{ flex: 1, gap: 4, padding: grid ? space.sm : 0 }}>
        <Text style={styles.name} numberOfLines={2}>{place.name}</Text>
        <View style={styles.inline}>
          <Text style={styles.tier}>{priceTier(place.price_level)}</Text>
          <Rating value={place.rating} />
        </View>
        {!grid && place.address ? <Text style={styles.muted} numberOfLines={1}>{place.address}</Text> : null}
        {isBudgetFriendly(place.price_level) ? <Badge label="Budget-friendly" icon="pricetag" /> : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  hotel: { backgroundColor: colors.card, borderRadius: radius.lg, overflow: 'hidden', borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  hotelImage: { height: 110, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
  row: {
    flexDirection: 'row', gap: space.md, padding: space.md, backgroundColor: colors.card, borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  tile: { flex: 1, backgroundColor: colors.card, borderRadius: radius.lg, overflow: 'hidden', borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  thumb: { width: 72, height: 72, borderRadius: radius.md, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
  name: { fontSize: 16, fontWeight: '700', color: colors.text },
  muted: { fontSize: 13, color: colors.muted },
  tier: { fontSize: 14, fontWeight: '700', color: colors.text },
  inline: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  ratingText: { fontSize: 14, fontWeight: '600', color: colors.text },
});
