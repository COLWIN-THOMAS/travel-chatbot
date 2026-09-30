import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, space } from '../lib/theme';
import type { DayForecast } from '../lib/types';
import type { IconName } from './ui';

const ICONS: Record<DayForecast['icon'], IconName> = {
  sun: 'sunny', partly: 'partly-sunny', cloud: 'cloudy', fog: 'cloud', rain: 'rainy', snow: 'snow', storm: 'thunderstorm',
};

export function WeatherWidget({ forecast, destination }: { forecast: DayForecast; destination?: string }) {
  const rainy = forecast.precipitation_probability >= 50;
  return (
    <View
      testID="weather-widget"
      accessibilityLabel={`Weather${destination ? ` in ${destination}` : ''}: ${forecast.condition}, ${Math.round(forecast.temp_max)} degrees. ${forecast.advisory}`}
      style={styles.card}
    >
      <View style={styles.iconWrap}>
        <Ionicons name={ICONS[forecast.icon] ?? 'partly-sunny'} size={34} color={colors.primaryDark} />
      </View>
      <View style={{ flex: 1, gap: 2 }}>
        <View style={styles.topRow}>
          <Text style={styles.temp}>{Math.round(forecast.temp_max)}°</Text>
          <Text style={styles.low}>/ {Math.round(forecast.temp_min)}°C</Text>
          <Text style={styles.cond}>{forecast.condition}</Text>
        </View>
        <Text style={[styles.meta, rainy && { color: colors.warn }]}>
          {forecast.precipitation_probability}% chance of rain
        </Text>
        <Text style={styles.advisory}>{forecast.advisory}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row', gap: space.md, alignItems: 'center', padding: space.lg,
    backgroundColor: '#E0F2FE', borderRadius: radius.lg,
  },
  iconWrap: { width: 56, height: 56, borderRadius: 28, backgroundColor: '#BAE6FD', alignItems: 'center', justifyContent: 'center' },
  topRow: { flexDirection: 'row', alignItems: 'baseline', gap: 6, flexWrap: 'wrap' },
  temp: { fontSize: 28, fontWeight: '800', color: colors.text },
  low: { fontSize: 14, color: colors.muted },
  cond: { fontSize: 15, fontWeight: '600', color: colors.text, marginLeft: space.sm },
  meta: { fontSize: 13, color: colors.muted },
  advisory: { fontSize: 13, color: colors.primaryDark, fontWeight: '600' },
});
