import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

/** Auth token: Keychain/Keystore on native; localStorage on web (SecureStore does not exist there). */
export const secureStore = {
  async get(key: string): Promise<string | null> {
    try {
      if (Platform.OS === 'web') return typeof localStorage === 'undefined' ? null : localStorage.getItem(key);
      return await SecureStore.getItemAsync(key);
    } catch { return null; }
  },
  async set(key: string, value: string): Promise<void> {
    try {
      if (Platform.OS === 'web') localStorage.setItem(key, value);
      else await SecureStore.setItemAsync(key, value);
    } catch { /* storage unavailable: user just has to sign in again next launch */ }
  },
  async remove(key: string): Promise<void> {
    try {
      if (Platform.OS === 'web') localStorage.removeItem(key);
      else await SecureStore.deleteItemAsync(key);
    } catch { /* ignore */ }
  },
};

/** Non-sensitive app state (chat session id, active trip). */
export const appStore = {
  async getJson<T>(key: string): Promise<T | null> {
    try {
      const raw = await AsyncStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : null;
    } catch { return null; }
  },
  async setJson(key: string, value: unknown): Promise<void> {
    try { await AsyncStorage.setItem(key, JSON.stringify(value)); } catch { /* ignore */ }
  },
  async remove(key: string): Promise<void> {
    try { await AsyncStorage.removeItem(key); } catch { /* ignore */ }
  },
};
