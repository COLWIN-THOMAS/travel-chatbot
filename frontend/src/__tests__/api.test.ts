import { api, ApiError, extractMessage, photoUrl, setAuthToken, setUnauthorizedHandler } from '../lib/api';
import { uuid4 } from '../lib/uuid';

// randomUUID is unavailable in insecure browser contexts; exercise the getRandomValues fallback with real entropy.
// jest.mock factories run before imports are bound, so they can only reference `require` (Jest allow-lists it).
jest.mock('expo-crypto', () => ({
  randomUUID: () => { throw new Error('crypto.randomUUID is not available'); },
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  getRandomValues: (a: Uint8Array) => require('crypto').randomFillSync(a),
}));

const mockFetch = (status: number, body?: unknown) =>
  jest.spyOn(global, 'fetch').mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === undefined ? '' : JSON.stringify(body)),
  } as Response);

afterEach(() => { jest.restoreAllMocks(); setAuthToken(null); setUnauthorizedHandler(null); });

describe('extractMessage', () => {
  it('reads string details, validation arrays and falls back sensibly', () => {
    expect(extractMessage({ detail: 'Trip not found' }, 404)).toBe('Trip not found');
    expect(extractMessage({ detail: [{ loc: ['body', 'days_count'], msg: 'Input should be less than or equal to 14' }] }, 422))
      .toBe('days count: Input should be less than or equal to 14');
    expect(extractMessage({ detail: [{ loc: ['body', 'password'], msg: 'Value error, password must be at most 72 bytes' }] }, 422))
      .toBe('password: password must be at most 72 bytes');
    expect(extractMessage(null, 500)).toMatch(/our side/);
    expect(extractMessage(null, 418)).toBe('Request failed (418)');
  });
});

describe('api()', () => {
  it('sends the bearer token and JSON body, returns parsed data', async () => {
    const f = mockFetch(200, { ok: true });
    setAuthToken('tok');
    await expect(api('/x', { method: 'POST', body: { a: 1 } })).resolves.toEqual({ ok: true });
    const init = f.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok');
    expect(init.body).toBe('{"a":1}');
  });

  it('does not attach the token to auth endpoints and does not treat their 401 as an expired session', async () => {
    mockFetch(401, { detail: 'Incorrect email or password' });
    const onExpired = jest.fn();
    setUnauthorizedHandler(onExpired);
    setAuthToken('tok');
    await expect(api('/auth/login', { method: 'POST', body: {}, auth: false })).rejects.toThrow('Incorrect email or password');
    expect(onExpired).not.toHaveBeenCalled();
    expect(((global.fetch as jest.Mock).mock.calls[0][1] as RequestInit).headers).not.toHaveProperty('Authorization');
  });

  it('signs the user out on a 401 from a protected endpoint', async () => {
    mockFetch(401, { detail: 'Not authenticated' });
    const onExpired = jest.fn();
    setUnauthorizedHandler(onExpired);
    await expect(api('/trips')).rejects.toBeInstanceOf(ApiError);
    expect(onExpired).toHaveBeenCalledTimes(1);
  });

  it('handles 204 and network failure', async () => {
    mockFetch(204);
    await expect(api('/x', { method: 'DELETE' })).resolves.toBeUndefined();
    jest.restoreAllMocks();
    jest.spyOn(global, 'fetch').mockRejectedValue(new TypeError('Network request failed'));
    await expect(api('/x')).rejects.toMatchObject({ status: 0, message: expect.stringMatching(/reach the server/) });
  });

  it('turns an abort into a timeout message', async () => {
    jest.spyOn(global, 'fetch').mockRejectedValue(Object.assign(new Error('aborted'), { name: 'AbortError' }));
    await expect(api('/x')).rejects.toMatchObject({ message: expect.stringMatching(/timed out/) });
  });
});

describe('photoUrl / uuid4', () => {
  it('prefixes relative photo links only', () => {
    expect(photoUrl('/places/photo?x=1')).toMatch(/^https?:\/\/.+\/places\/photo\?x=1$/);
    expect(photoUrl('https://cdn.example/p.jpg')).toBe('https://cdn.example/p.jpg');
  });
  it('produces valid, unique v4 ids', () => {
    const a = uuid4();
    expect(a).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(uuid4()).not.toBe(a);
  });
});
