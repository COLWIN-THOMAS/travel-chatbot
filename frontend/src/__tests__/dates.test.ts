import {
  addDays, diffDays, formatLong, formatRange, formatShort, monthGrid, monthTitle, parseISO, shiftMonth, todayISO, toISO,
} from '../lib/dates';

describe('parseISO', () => {
  it('parses valid dates and rejects impossible ones', () => {
    expect(parseISO('2026-11-14')).toEqual({ y: 2026, m0: 10, d: 14 });
    expect(parseISO('2026-02-31')).toBeNull();
    expect(parseISO('banana')).toBeNull();
    expect(parseISO(null)).toBeNull();
  });
});

describe('date arithmetic', () => {
  it('adds days across month and year boundaries', () => {
    expect(addDays('2026-11-28', 4)).toBe('2026-12-02');
    expect(addDays('2026-12-30', 3)).toBe('2027-01-02');
    expect(addDays('2028-02-28', 1)).toBe('2028-02-29'); // leap year
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28');
  });
  it('is not affected by daylight-saving shifts', () => {
    expect(addDays('2026-03-28', 2)).toBe('2026-03-30');
    expect(diffDays('2026-10-24', '2026-10-26')).toBe(2);
  });
  it('diffDays is signed', () => {
    expect(diffDays('2026-11-10', '2026-11-14')).toBe(4);
    expect(diffDays('2026-11-14', '2026-11-10')).toBe(-4);
  });
  it('todayISO formats a local date with zero padding', () => {
    expect(todayISO(new Date(2026, 0, 5))).toBe('2026-01-05');
    expect(toISO(2026, 11, 31)).toBe('2026-12-31');
  });
});

describe('formatting', () => {
  it('formats single dates with weekday', () => {
    expect(formatLong('2026-11-14')).toBe('Sat 14 Nov 2026');
    expect(formatShort('2026-11-14', 2026)).toBe('Sat 14 Nov');
    expect(formatShort('2027-01-02', 2026)).toBe('Sat 2 Jan 2027');
    expect(formatShort(null)).toBe('');
  });
  it('formats ranges compactly', () => {
    expect(formatRange('2026-11-14', '2026-11-17')).toBe('14 – 17 Nov 2026');
    expect(formatRange('2026-11-28', '2026-12-02')).toBe('28 Nov – 2 Dec 2026');
    expect(formatRange('2026-12-30', '2027-01-02')).toBe('30 Dec 2026 – 2 Jan 2027');
    expect(formatRange('2026-11-14', '2026-11-14')).toBe('14 Nov 2026');
    expect(formatRange('2026-11-14', null)).toBe('14 Nov 2026');
    expect(formatRange(null, null)).toBe('');
  });
});

describe('calendar grid', () => {
  it('lays November 2026 out Sunday-first (1 Nov 2026 is a Sunday)', () => {
    const weeks = monthGrid(2026, 10);
    expect(weeks[0]).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(weeks[weeks.length - 1].filter((d) => d !== null).pop()).toBe(30);
    expect(weeks.every((w) => w.length === 7)).toBe(true);
  });
  it('pads the first week when the month starts mid-week', () => {
    const weeks = monthGrid(2026, 9); // 1 Oct 2026 is a Thursday
    expect(weeks[0]).toEqual([null, null, null, null, 1, 2, 3]);
    expect(weeks.flat().filter((d) => d !== null)).toHaveLength(31);
  });
  it('handles February in a leap year', () => {
    expect(monthGrid(2028, 1).flat().filter((d) => d !== null)).toHaveLength(29);
  });
  it('shifts months across year boundaries', () => {
    expect(shiftMonth(2026, 11, 1)).toEqual({ y: 2027, m0: 0 });
    expect(shiftMonth(2026, 0, -1)).toEqual({ y: 2025, m0: 11 });
    expect(monthTitle(2026, 10)).toBe('November 2026');
  });
});
