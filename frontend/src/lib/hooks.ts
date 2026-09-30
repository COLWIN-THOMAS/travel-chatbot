import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo } from 'react';
import { api, ApiError } from './api';
import { useChatSession } from './session';
import type {
  ChatHistory, ChatMessage, ChatResponse, Expense, ExpenseLogResponse, Itinerary, ItineraryItem, PlaceCategory,
  PlaceDetail, PlaceSummary, TrackerSummary, Trip, Weather,
} from './types';

const MIN = 60 * 1000;

export const keys = {
  trips: ['trips'] as const,
  itinerary: (tripId: string) => ['itinerary', tripId] as const,
  tracker: (tripId: string) => ['tracker', tripId] as const,
  expenses: (tripId: string) => ['expenses', tripId] as const,
  places: (tripId: string, category: PlaceCategory) => ['places', tripId, category] as const,
  place: (placeId: string) => ['place', placeId] as const,
  weather: (tripId: string) => ['weather', tripId] as const,
  chat: (sessionId: string) => ['chat', sessionId] as const,
};

/* ---------- trips ---------- */

export function useTrips() {
  return useQuery({ queryKey: keys.trips, queryFn: () => api<Trip[]>('/trips'), staleTime: MIN });
}

/** The trip the Plan / Tracker / Explore tabs operate on: the stored choice, else the newest trip. */
export function useActiveTrip() {
  const { activeTripId, ready } = useChatSession();
  const trips = useTrips();
  const trip = useMemo(() => {
    const list = trips.data ?? [];
    return list.find((t) => t.id === activeTripId) ?? list[0];
  }, [trips.data, activeTripId]);
  return { trip, isLoading: !ready || trips.isLoading, error: trips.error, refetch: trips.refetch };
}

export function useDeleteTrip() {
  const qc = useQueryClient();
  const { activeTripId, setActiveTripId } = useChatSession();
  return useMutation({
    mutationFn: (tripId: string) => api<void>(`/trips/${tripId}`, { method: 'DELETE' }),
    onSuccess: (_d, tripId) => {
      if (activeTripId === tripId) setActiveTripId(null);
      qc.removeQueries({ queryKey: keys.itinerary(tripId) });
      qc.removeQueries({ queryKey: keys.tracker(tripId) });
      void qc.invalidateQueries({ queryKey: keys.trips });
    },
  });
}

/* ---------- itinerary / tracker ---------- */

export function useItinerary(tripId?: string) {
  return useQuery({
    queryKey: keys.itinerary(tripId ?? ''),
    queryFn: () => api<Itinerary>(`/itinerary/${tripId}`),
    enabled: !!tripId,
  });
}

export function useTracker(tripId?: string) {
  return useQuery({
    queryKey: keys.tracker(tripId ?? ''),
    queryFn: () => api<TrackerSummary>(`/tracker/${tripId}`),
    enabled: !!tripId,
  });
}

export function useExpenses(tripId?: string) {
  return useQuery({
    queryKey: keys.expenses(tripId ?? ''),
    queryFn: () => api<Expense[]>(`/tracker/${tripId}/expenses`),
    enabled: !!tripId,
  });
}

function refreshTripData(qc: ReturnType<typeof useQueryClient>, tripId: string) {
  void qc.invalidateQueries({ queryKey: keys.itinerary(tripId) });
  void qc.invalidateQueries({ queryKey: keys.tracker(tripId) });
  void qc.invalidateQueries({ queryKey: keys.expenses(tripId) });
}

export function useToggleVisited(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { itemId: string; visited: boolean }) =>
      api<ItineraryItem>(`/tracker/${tripId}/visit`, { method: 'POST', body: { itinerary_item_id: v.itemId, visited: v.visited } }),
    // Optimistic: the checkbox flips instantly and rolls back if the server rejects it.
    onMutate: async (v) => {
      await qc.cancelQueries({ queryKey: keys.itinerary(tripId) });
      const prev = qc.getQueryData<Itinerary>(keys.itinerary(tripId));
      if (prev) {
        qc.setQueryData<Itinerary>(keys.itinerary(tripId), {
          days: prev.days.map((d) => ({
            ...d,
            items: d.items.map((i) => (i.id === v.itemId ? { ...i, visited: v.visited } : i)),
          })),
        });
      }
      return { prev };
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(keys.itinerary(tripId), ctx.prev); },
    onSettled: () => refreshTripData(qc, tripId),
  });
}

export function useLogExpense(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { amount: number; category?: string; itemId?: string }) =>
      api<ExpenseLogResponse>(`/tracker/${tripId}/expense`, {
        method: 'POST',
        body: { amount: v.amount, category: v.category ?? null, itinerary_item_id: v.itemId ?? null },
      }),
    onSuccess: () => refreshTripData(qc, tripId),
  });
}

export function useDeleteExpense(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (expenseId: string) => api<void>(`/tracker/${tripId}/expense/${expenseId}`, { method: 'DELETE' }),
    onSuccess: () => refreshTripData(qc, tripId),
  });
}

export function useRegenerate(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (instructions: string) =>
      api<Itinerary>(`/itinerary/${tripId}/regenerate`, {
        method: 'POST',
        body: { changes: instructions ? { instructions } : {} },
        timeoutMs: 150000,
      }),
    onSuccess: () => refreshTripData(qc, tripId),
  });
}

/* ---------- places / weather ---------- */

export function usePlaces(tripId: string | undefined, category: PlaceCategory) {
  return useQuery({
    queryKey: keys.places(tripId ?? '', category),
    queryFn: async () => (await api<{ places: PlaceSummary[] }>(`/places/${tripId}?category=${category}`)).places,
    enabled: !!tripId,
    staleTime: 10 * MIN,
  });
}

export function usePlaceDetail(placeId: string) {
  return useQuery({
    queryKey: keys.place(placeId),
    queryFn: () => api<PlaceDetail>(`/places/detail/${encodeURIComponent(placeId)}`),
    staleTime: 10 * MIN,
  });
}

export function useWeather(tripId?: string) {
  return useQuery({
    queryKey: keys.weather(tripId ?? ''),
    queryFn: () => api<Weather>(`/weather/${tripId}`),
    enabled: !!tripId,
    staleTime: 30 * MIN,
    retry: 1,
  });
}

/* ---------- chat ---------- */

const emptyHistory = (sessionId: string): ChatHistory => ({
  session_id: sessionId, state: 'COLLECTING', slots: {}, trip_id: null, messages: [],
});

export function useChat() {
  const qc = useQueryClient();
  const { sessionId, setActiveTripId } = useChatSession();
  const key = keys.chat(sessionId);

  const history = useQuery({
    queryKey: key,
    queryFn: async () => {
      try {
        return await api<ChatHistory>(`/chat/${sessionId}`);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return emptyHistory(sessionId); // brand-new session
        throw e;
      }
    },
    staleTime: Infinity,
  });

  const send = useMutation({
    // A plan can take a minute to build, so this call gets a long timeout.
    mutationFn: (text: string) =>
      api<ChatResponse>('/chat', { method: 'POST', body: { session_id: sessionId, message: text }, timeoutMs: 150000 }),
    onMutate: async (text) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<ChatHistory>(key) ?? emptyHistory(sessionId);
      const pending: ChatMessage = { role: 'user', content: text, pending: true };
      qc.setQueryData<ChatHistory>(key, { ...prev, messages: [...prev.messages, pending] });
      return { prev };
    },
    onError: (_e, _text, ctx) => { if (ctx) qc.setQueryData(key, ctx.prev); },
    onSuccess: (res, text, ctx) => {
      const prev = ctx?.prev ?? emptyHistory(sessionId);
      const state = res.conversation_state === 'FALLBACK' ? prev.state
        : res.conversation_state === 'GENERATE_PLAN' ? 'POST_PLAN' : res.conversation_state;
      qc.setQueryData<ChatHistory>(key, {
        ...prev,
        state,
        slots: res.extracted_fields,
        trip_id: res.trip_id,
        messages: [...prev.messages, { role: 'user', content: text }, { role: 'assistant', content: res.reply_text }],
      });
      if (res.trip_id) {
        setActiveTripId(res.trip_id);
        void qc.invalidateQueries({ queryKey: keys.trips });
        if (res.itinerary || res.actions.length > 0) refreshTripData(qc, res.trip_id);
      }
    },
  });

  const sendMessage = useCallback((text: string) => send.mutateAsync(text), [send]);
  return {
    messages: history.data?.messages ?? [],
    state: history.data?.state ?? 'COLLECTING',
    slots: history.data?.slots ?? {},
    tripId: history.data?.trip_id ?? null,
    isLoading: history.isLoading,
    loadError: history.error,
    sending: send.isPending,
    sendError: send.error as Error | null,
    clearSendError: send.reset,
    sendMessage,
  };
}
