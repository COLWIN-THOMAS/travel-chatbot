import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { inr } from '../lib/format';
import { categoryMeta, colors, radius, space } from '../lib/theme';
import type { ItineraryItem } from '../lib/types';

interface Props {
  item: ItineraryItem;
  onToggle: (visited: boolean) => void;
  onAddExpense?: () => void;
  disabled?: boolean;
}

export function ChecklistItem({ item, onToggle, onAddExpense, disabled }: Props) {
  const meta = categoryMeta[item.category];
  const over = item.actual_cost > item.estimated_cost && item.estimated_cost > 0;
  return (
    <View style={styles.row}>
      <Pressable
        testID={`visit-${item.id}`}
        accessibilityRole="checkbox"
        accessibilityLabel={`${item.place_name}, ${item.visited ? 'visited' : 'not visited'}`}
        accessibilityState={{ checked: item.visited, disabled }}
        disabled={disabled}
        hitSlop={8}
        onPress={() => onToggle(!item.visited)}
        style={[styles.box, item.visited && styles.boxOn]}
      >
        {item.visited ? <Ionicons name="checkmark" size={18} color="#fff" /> : null}
      </Pressable>

      <View style={{ flex: 1, gap: 2 }}>
        <Text style={[styles.name, item.visited && styles.done]} numberOfLines={2}>{item.place_name}</Text>
        <View style={styles.meta}>
          <Ionicons name={meta.icon as React.ComponentProps<typeof Ionicons>['name']} size={13} color={colors.muted} />
          <Text style={styles.metaText}>{meta.label}</Text>
          <Text style={styles.metaText}>{'•'} est {inr(item.estimated_cost)}</Text>
          {item.actual_cost > 0 ? (
            <Text style={[styles.metaText, { color: over ? colors.danger : colors.success, fontWeight: '700' }]}>
              {'•'} spent {inr(item.actual_cost)}
            </Text>
          ) : null}
        </View>
      </View>

      {onAddExpense ? (
        <Pressable
          testID={`expense-for-${item.id}`}
          accessibilityRole="button"
          accessibilityLabel={`Log expense for ${item.place_name}`}
          hitSlop={8}
          onPress={onAddExpense}
          style={styles.add}
        >
          <Ionicons name="add" size={20} color={colors.primary} />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md, paddingVertical: space.sm },
  box: { width: 28, height: 28, borderRadius: 8, borderWidth: 2, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', backgroundColor: '#fff' },
  boxOn: { backgroundColor: colors.success, borderColor: colors.success },
  name: { fontSize: 15, fontWeight: '600', color: colors.text },
  done: { textDecorationLine: 'line-through', color: colors.muted },
  meta: { flexDirection: 'row', alignItems: 'center', gap: 4, flexWrap: 'wrap' },
  metaText: { fontSize: 12, color: colors.muted },
  add: { width: 36, height: 36, borderRadius: radius.pill, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
});
