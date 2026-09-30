import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React from 'react';
import { Pressable, View } from 'react-native';
import { colors, space } from '../lib/theme';

export function HeaderActions({ onNewChat }: { onNewChat?: () => void }) {
  return (
    <View style={{ flexDirection: 'row', gap: space.md, marginRight: space.md }}>
      {onNewChat ? (
        <Pressable testID="new-chat" accessibilityRole="button" accessibilityLabel="Start a new chat" hitSlop={8} onPress={onNewChat}>
          <Ionicons name="create-outline" size={24} color={colors.primaryDark} />
        </Pressable>
      ) : null}
      <Pressable testID="open-trips" accessibilityRole="button" accessibilityLabel="My trips" hitSlop={8} onPress={() => router.push('/trips')}>
        <Ionicons name="albums-outline" size={24} color={colors.primaryDark} />
      </Pressable>
    </View>
  );
}
