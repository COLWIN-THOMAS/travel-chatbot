import { useQueryClient } from '@tanstack/react-query';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, ApiError, setAuthToken, setUnauthorizedHandler } from './api';
import { secureStore } from './storage';
import type { TokenResponse, User } from './types';

const TOKEN_KEY = 'auth_token';

type Status = 'loading' | 'signedOut' | 'signedIn' | 'error';

interface AuthContextValue {
  status: Status;
  user: User | null;
  bootError: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  deleteAccount: (password: string) => Promise<void>;
  retryBoot: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<Status>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);
  const [bootAttempt, setBootAttempt] = useState(0);

  const signOut = useCallback(async () => {
    await secureStore.remove(TOKEN_KEY);
    setAuthToken(null);
    queryClient.clear();
    setUser(null);
    setStatus('signedOut');
  }, [queryClient]);

  useEffect(() => {
    setUnauthorizedHandler(() => { void signOut(); });
    return () => setUnauthorizedHandler(null);
  }, [signOut]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setStatus('loading');
      const token = await secureStore.get(TOKEN_KEY);
      if (!token) { if (!cancelled) setStatus('signedOut'); return; }
      setAuthToken(token);
      try {
        const me = await api<User>('/auth/me');
        if (!cancelled) { setUser(me); setStatus('signedIn'); }
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 401) { await signOut(); return; }
        setBootError(e instanceof Error ? e.message : 'Could not reach the server');
        setStatus('error');
      }
    })();
    return () => { cancelled = true; };
  }, [bootAttempt, signOut]);

  const finish = useCallback(async (res: TokenResponse) => {
    await secureStore.set(TOKEN_KEY, res.access_token);
    setAuthToken(res.access_token);
    queryClient.clear();
    setUser(res.user);
    setStatus('signedIn');
  }, [queryClient]);

  const signIn = useCallback(async (email: string, password: string) => {
    await finish(await api<TokenResponse>('/auth/login', { method: 'POST', body: { email: email.trim(), password }, auth: false }));
  }, [finish]);

  const register = useCallback(async (email: string, password: string) => {
    await finish(await api<TokenResponse>('/auth/register', { method: 'POST', body: { email: email.trim(), password }, auth: false }));
  }, [finish]);

  const retryBoot = useCallback(() => { setBootError(null); setBootAttempt((n) => n + 1); }, []);

  // Throws on a wrong password (caller shows the message); only signs out once the account is
  // actually gone server-side, never optimistically.
  const deleteAccount = useCallback(async (password: string) => {
    await api<void>('/auth/me', { method: 'DELETE', body: { password } });
    await signOut();
  }, [signOut]);

  const value = useMemo(
    () => ({ status, user, bootError, signIn, register, signOut, deleteAccount, retryBoot }),
    [status, user, bootError, signIn, register, signOut, deleteAccount, retryBoot],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
