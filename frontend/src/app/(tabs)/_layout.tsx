import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router/js-tabs';
import React from 'react';
import type { ColorValue } from 'react-native';
import { HeaderActions } from '../../components/HeaderActions';
import { colors } from '../../lib/theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

const tab = (title: string, icon: IconName, iconActive: IconName) => ({
  title,
  tabBarIcon: ({ focused, color, size }: { focused: boolean; color: ColorValue; size: number }) => (
    <Ionicons name={focused ? iconActive : icon} size={size} color={color} />
  ),
});

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.muted,
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: '700' },
        sceneStyle: { backgroundColor: colors.bg },
        headerRight: () => <HeaderActions />,
      }}
    >
      <Tabs.Screen name="index" options={tab('Assistant', 'chatbubbles-outline', 'chatbubbles')} />
      <Tabs.Screen name="plan" options={tab('Plan', 'map-outline', 'map')} />
      <Tabs.Screen name="tracker" options={tab('Tracker', 'wallet-outline', 'wallet')} />
      <Tabs.Screen name="explore" options={tab('Explore', 'compass-outline', 'compass')} />
    </Tabs>
  );
}
