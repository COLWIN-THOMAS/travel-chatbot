/**
 * Calendar helpers. Dates travel as plain "YYYY-MM-DD" strings (what the API sends) and all arithmetic is done on
 * UTC components, so a device's timezone / DST can never shift a trip day.
 */
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const MONTHS_SHORT = MONTHS.map((m) => m.slice(0, 3));
const WEEKDAYS_SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const WEEKDAY_HEADERS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

const pad = (n: number) => String(n).padStart(2, '0');

export function toISO(year: number, month0: number, day: number): string {
  return `${year}-${pad(month0 + 1)}-${pad(day)}`;
}

export function parseISO(iso: string | null | undefined): { y: number; m0: number; d: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? '');
  if (!match) return null;
  const y = Number(match[1]), m0 = Number(match[2]) - 1, d = Number(match[3]);
  const check = new Date(Date.UTC(y, m0, d));
  if (check.getUTCFullYear() !== y || check.getUTCMonth() !== m0 || check.getUTCDate() !== d) return null; // e.g. 2026-02-31
  return { y, m0, d };
}

/** Today's date on the device, as YYYY-MM-DD. */
export function todayISO(now: Date = new Date()): string {
  return toISO(now.getFullYear(), now.getMonth(), now.getDate());
}

export function addDays(iso: string, n: number): string {
  const p = parseISO(iso);
  if (!p) return iso;
  const t = new Date(Date.UTC(p.y, p.m0, p.d + n));
  return toISO(t.getUTCFullYear(), t.getUTCMonth(), t.getUTCDate());
}

/** Whole days from a to b (negative if b is earlier). */
export function diffDays(a: string, b: string): number {
  const pa = parseISO(a), pb = parseISO(b);
  if (!pa || !pb) return 0;
  return Math.round((Date.UTC(pb.y, pb.m0, pb.d) - Date.UTC(pa.y, pa.m0, pa.d)) / 86_400_000);
}

export function weekdayOf(iso: string): number {
  const p = parseISO(iso);
  return p ? new Date(Date.UTC(p.y, p.m0, p.d)).getUTCDay() : 0;
}

/** "Sat 14 Nov" (adds the year when it isn't `currentYear`). */
export function formatShort(iso: string | null | undefined, currentYear: number = new Date().getFullYear()): string {
  const p = parseISO(iso);
  if (!p) return '';
  const base = `${WEEKDAYS_SHORT[weekdayOf(iso as string)]} ${p.d} ${MONTHS_SHORT[p.m0]}`;
  return p.y === currentYear ? base : `${base} ${p.y}`;
}

/** "Sat 14 Nov 2026" */
export function formatLong(iso: string | null | undefined): string {
  const p = parseISO(iso);
  return p ? `${WEEKDAYS_SHORT[weekdayOf(iso as string)]} ${p.d} ${MONTHS_SHORT[p.m0]} ${p.y}` : '';
}

/** "14 – 17 Nov 2026", "28 Nov – 2 Dec 2026", or a single date for one-day trips. */
export function formatRange(startISO: string | null | undefined, endISO: string | null | undefined): string {
  const s = parseISO(startISO), e = parseISO(endISO ?? startISO);
  if (!s || !e) return '';
  if (s.y === e.y && s.m0 === e.m0 && s.d === e.d) return `${s.d} ${MONTHS_SHORT[s.m0]} ${s.y}`;
  if (s.y === e.y && s.m0 === e.m0) return `${s.d} – ${e.d} ${MONTHS_SHORT[s.m0]} ${s.y}`;
  if (s.y === e.y) return `${s.d} ${MONTHS_SHORT[s.m0]} – ${e.d} ${MONTHS_SHORT[e.m0]} ${s.y}`;
  return `${s.d} ${MONTHS_SHORT[s.m0]} ${s.y} – ${e.d} ${MONTHS_SHORT[e.m0]} ${e.y}`;
}

export function monthTitle(year: number, month0: number): string {
  return `${MONTHS[month0]} ${year}`;
}

/** Shifts a (year, month) pair by `delta` months. */
export function shiftMonth(year: number, month0: number, delta: number): { y: number; m0: number } {
  const index = year * 12 + month0 + delta;
  return { y: Math.floor(index / 12), m0: ((index % 12) + 12) % 12 };
}

/** The calendar grid for a month: weeks (Sunday first) of day-of-month numbers, with null for padding cells. */
export function monthGrid(year: number, month0: number): (number | null)[][] {
  const first = new Date(Date.UTC(year, month0, 1)).getUTCDay();
  const count = new Date(Date.UTC(year, month0 + 1, 0)).getUTCDate();
  const cells: (number | null)[] = [...Array<null>(first).fill(null), ...Array.from({ length: count }, (_, i) => i + 1)];
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks: (number | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return weeks;
}
