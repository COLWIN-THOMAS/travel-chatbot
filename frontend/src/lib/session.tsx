import { uuid4 } from './uuid';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useAuth } from './auth';
import { appStore } from './storage';

interface Persisted { sessionId: string; activeTripId: string | null }

interface SessionValue {
  ready: boolean;
  sessionId: string;
  activeTripId: string | null;
  setActiveTripId: (id: string | null) => void;
  newChat: () => void;
}

const SessionContext = createContext<SessionValue | null>(null);

/** Per-user chat session id (generated client-side, as the API contract requires) and the trip the tabs show. */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const storageKey = user ? `chat:${user.id}` : null;
  const [ready, setReady] = useState(false);
  const [state, setState] = useState<Persisted>({ sessionId: uuid4(), activeTripId: null });

  useEffect(() => {
    if (!storageKey) return;
    let cancelled = false;
    setReady(false);
    appStore.getJson<Persisted>(storageKey).then((saved) => {
      if (cancelled) return;
      if (saved?.sessionId) setState({ sessionId: saved.sessionId, activeTripId: saved.activeTripId ?? null });
      else setState({ sessionId: uuid4(), activeTripId: null });
      setReady(true);
    });
    return () => { cancelled = true; };
  }, [storageKey]);

  const update = useCallback((next: Persisted) => {
    setState(next);
    if (storageKey) void appStore.setJson(storageKey, next);
  }, [storageKey]);

  const setActiveTripId = useCallback((id: string | null) => update({ ...state, activeTripId: id }), [state, update]);
  const newChat = useCallback(() => update({ ...state, sessionId: uuid4() }), [state, update]);

  const value = useMemo(
    () => ({ ready, sessionId: state.sessionId, activeTripId: state.activeTripId, setActiveTripId, newChat }),
    [ready, state, setActiveTripId, newChat],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useChatSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useChatSession must be used inside SessionProvider');
  return ctx;
}
