export const colors = {
  primary: '#0F766E',
  primaryDark: '#115E59',
  primarySoft: '#CCFBF1',
  accent: '#F59E0B',
  bg: '#F5F7F8',
  card: '#FFFFFF',
  text: '#111827',
  muted: '#6B7280',
  border: '#E5E7EB',
  success: '#15803D',
  successSoft: '#DCFCE7',
  warn: '#B45309',
  warnSoft: '#FEF3C7',
  danger: '#B91C1C',
  dangerSoft: '#FEE2E2',
  userBubble: '#0F766E',
  botBubble: '#FFFFFF',
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 } as const;
export const radius = { sm: 8, md: 12, lg: 16, pill: 999 } as const;

export const categoryMeta = {
  hotel: { icon: 'bed-outline', label: 'Stay' },
  restaurant: { icon: 'restaurant-outline', label: 'Food' },
  attraction: { icon: 'camera-outline', label: 'See' },
  transport: { icon: 'bus-outline', label: 'Travel' },
} as const;
