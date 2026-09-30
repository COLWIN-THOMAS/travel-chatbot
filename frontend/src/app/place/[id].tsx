import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { Stack, useLocalSearchParams } from 'expo-router';
import React, { useState } from 'react';
import { FlatList, Linking, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { Badge, Button, Card, SectionTitle, StateView } from '../../components/ui';
import { photoUrl } from '../../lib/api';
import { isBudgetFriendly, priceTier } from '../../lib/format';
import { usePlaceDetail } from '../../lib/hooks';
import { colors, space } from '../../lib/theme';

const HERO_HEIGHT = 240;
const REVIEWS_COLLAPSED = 3;

function InfoRow({ icon, text, onPress, label }: { icon: React.ComponentProps<typeof Ionicons>['name']; text: string; onPress?: () => void; label: string }) {
  return (
    <Pressable
      accessibilityRole={onPress ? 'link' : 'text'}
      accessibilityLabel={`${label}: ${text}`}
      disabled={!onPress}
      onPress={onPress}
      style={styles.infoRow}
    >
      <Ionicons name={icon} size={20} color={colors.primary} />
      <Text style={[styles.infoText, onPress && { color: colors.primary }]} numberOfLines={3}>{text}</Text>
    </Pressable>
  );
}

export default function PlaceDetailScreen() {
  const { id, name } = useLocalSearchParams<{ id: string; name?: string }>();
  const place = usePlaceDetail(String(id));
  const { width } = useWindowDimensions();
  const [photoIndex, setPhotoIndex] = useState(0);
  const [allReviews, setAllReviews] = useState(false);
  const [hoursOpen, setHoursOpen] = useState(false);

  const title = place.data?.name ?? name ?? 'Place details';
  if (place.isLoading || place.error) {
    return (
      <>
        <Stack.Screen options={{ title }} />
        <StateView loading={place.isLoading} error={place.error} onRetry={() => place.refetch()} />
      </>
    );
  }

  const p = place.data!;
  const todayIndex = (new Date().getDay() + 6) % 7; // Google lists Monday first
  const hours = p.opening_hours ?? [];
  const reviews = allReviews ? p.reviews : p.reviews.slice(0, REVIEWS_COLLAPSED);
  const website = p.website && /^https?:\/\//i.test(p.website) ? p.website : null;

  return (
    <>
      <Stack.Screen options={{ title }} />
      <ScrollView testID="place-detail" contentContainerStyle={{ paddingBottom: space.xl * 2 }}>
        {p.photos.length > 0 ? (
          <View>
            <FlatList
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              data={p.photos}
              keyExtractor={(u) => u}
              onMomentumScrollEnd={(e) => setPhotoIndex(Math.round(e.nativeEvent.contentOffset.x / width))}
              renderItem={({ item }) => (
                <Image
                  source={{ uri: photoUrl(item) }}
                  accessibilityLabel={`Photo of ${p.name}`}
                  style={{ width, height: HERO_HEIGHT, backgroundColor: colors.border }}
                  contentFit="cover"
                  transition={150}
                />
              )}
            />
            {p.photos.length > 1 ? (
              <View style={styles.dots} accessibilityLabel={`Photo ${photoIndex + 1} of ${p.photos.length}`}>
                {p.photos.map((u, i) => <View key={u} style={[styles.dot, i === photoIndex && styles.dotOn]} />)}
              </View>
            ) : null}
          </View>
        ) : (
          <View style={[styles.hero, { height: HERO_HEIGHT }]}>
            <Ionicons name="image-outline" size={48} color={colors.primary} />
            <Text style={styles.muted}>No photos available</Text>
          </View>
        )}

        <View style={{ padding: space.lg, gap: space.md }}>
          <Text accessibilityRole="header" style={styles.name}>{p.name}</Text>
          <View style={styles.metaRow}>
            {p.rating != null ? (
              <View style={styles.inline}>
                <Ionicons name="star" size={16} color={colors.accent} />
                <Text style={styles.rating}>{p.rating.toFixed(1)}</Text>
              </View>
            ) : null}
            <Text style={styles.tier}>{priceTier(p.price_level)}</Text>
            {isBudgetFriendly(p.price_level) ? <Badge label="Budget-friendly" icon="pricetag" /> : null}
          </View>
          {p.description ? <Text style={styles.description}>{p.description}</Text> : null}

          <Card style={{ gap: space.sm }}>
            {p.address ? <InfoRow icon="location-outline" label="Address" text={p.address} /> : null}
            {p.phone ? <InfoRow icon="call-outline" label="Phone" text={p.phone} onPress={() => Linking.openURL(`tel:${p.phone!.replace(/[^\d+]/g, '')}`)} /> : null}
            {website ? <InfoRow icon="globe-outline" label="Website" text={website.replace(/^https?:\/\//i, '')} onPress={() => Linking.openURL(website)} /> : null}
            {hours.length > 0 ? (
              <View style={{ gap: 4 }}>
                <Pressable accessibilityRole="button" accessibilityState={{ expanded: hoursOpen }} onPress={() => setHoursOpen((o) => !o)} style={styles.infoRow}>
                  <Ionicons name="time-outline" size={20} color={colors.primary} />
                  <Text style={[styles.infoText, { flex: 1 }]}>{hours[todayIndex] ?? 'Opening hours'}</Text>
                  <Ionicons name={hoursOpen ? 'chevron-up' : 'chevron-down'} size={18} color={colors.muted} />
                </Pressable>
                {hoursOpen ? hours.map((h, i) => (
                  <Text key={h} style={[styles.hour, i === todayIndex && { fontWeight: '700', color: colors.text }]}>{h}</Text>
                )) : null}
              </View>
            ) : null}
          </Card>

          {p.reviews.length > 0 ? (
            <>
              <SectionTitle>Reviews</SectionTitle>
              {reviews.map((r, i) => (
                <Card key={`${r.author_name}-${i}`} style={{ gap: 6 }}>
                  <View style={styles.metaRow}>
                    <Text style={styles.author}>{r.author_name ?? 'Visitor'}</Text>
                    {r.rating != null ? <Text style={styles.muted}>{'\u2605'.repeat(Math.round(r.rating))}</Text> : null}
                  </View>
                  {r.text ? <Text style={styles.reviewText} numberOfLines={allReviews ? undefined : 6}>{r.text}</Text> : null}
                </Card>
              ))}
              {!allReviews && p.reviews.length > REVIEWS_COLLAPSED ? (
                <Button label={`Show all ${p.reviews.length} reviews`} variant="secondary" onPress={() => setAllReviews(true)} />
              ) : null}
            </>
          ) : null}
        </View>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  hero: { backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center', gap: space.sm },
  dots: { position: 'absolute', bottom: 10, alignSelf: 'center', flexDirection: 'row', gap: 6 },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.6)' },
  dotOn: { backgroundColor: '#fff', width: 9, height: 9, borderRadius: 5 },
  name: { fontSize: 24, fontWeight: '800', color: colors.text },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: space.md, flexWrap: 'wrap' },
  inline: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  rating: { fontSize: 16, fontWeight: '700', color: colors.text },
  tier: { fontSize: 16, fontWeight: '700', color: colors.text },
  description: { fontSize: 15, lineHeight: 22, color: colors.text },
  infoRow: { flexDirection: 'row', alignItems: 'center', gap: space.md, minHeight: 32 },
  infoText: { fontSize: 15, color: colors.text, flexShrink: 1 },
  hour: { fontSize: 13, color: colors.muted, marginLeft: 32 },
  author: { fontSize: 14, fontWeight: '700', color: colors.text },
  reviewText: { fontSize: 14, lineHeight: 20, color: colors.text },
  muted: { fontSize: 13, color: colors.muted },
});
