import { router } from 'expo-router';
import React from 'react';
import { StateView } from './ui';

export function NoTrip() {
  return (
    <StateView
      emptyTitle="No trip yet"
      emptyBody="Chat with the assistant – tell it where you're going, your budget and how many days – and your plan will appear here."
      action={{ label: 'Plan a trip', onPress: () => router.navigate('/') }}
    />
  );
}
