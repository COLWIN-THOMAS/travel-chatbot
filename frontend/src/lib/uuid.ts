import * as Crypto from 'expo-crypto';

/** RFC 4122 v4. crypto.randomUUID needs a secure context (missing on http://<lan-ip> in web dev), so fall back to getRandomValues. */
export function uuid4(): string {
  try {
    const id = Crypto.randomUUID();
    if (id) return id;
  } catch { /* fall through */ }
  const b = Crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}
