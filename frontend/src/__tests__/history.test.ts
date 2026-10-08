import { groupTrips, historyTotals, phaseLabel } from '../lib/history';
import type { TripPhase, TripSummary } from '../lib/types';

let n = 0;
function trip(phase: TripPhase, start: string | null, extra: Partial<TripSummary> = {}): TripSummary {
  n += 1;
  return {
    id: `t${n}`, user_id: 'u', destination: `Place ${n}`, budget_total: 10000, days_count: 3,
    start_date: start, end_date: start, phase, preferences: null, status: 'active',
    created_at: `2026-09-${String(10 + n).padStart(2, '0')}T00:00:00Z`,
    estimated_total: 9000, spend_total: 0, items_total: 10, items_visited: 0, ...extra,
  };
}

describe('groupTrips', () => {
  it('splits into happening now / upcoming / past and drops empty sections', () => {
    const sections = groupTrips([trip('completed', '2026-08-01'), trip('upcoming', '2026-12-01')]);
    expect(sections.map((s) => s.key)).toEqual(['upcoming', 'past']);
  });

  it('orders upcoming by date with undated trips last, and past trips newest first', () => {
    const later = trip('upcoming', '2027-01-10');
    const sooner = trip('upcoming', '2026-11-20');
    const undated = trip('undated', null);
    const old = trip('completed', '2026-03-01');
    const recent = trip('completed', '2026-08-15');
    const sections = groupTrips([old, later, undated, recent, sooner]);
    expect(sections.find((s) => s.key === 'upcoming')!.data.map((t) => t.id)).toEqual([sooner.id, later.id, undated.id]);
    expect(sections.find((s) => s.key === 'past')!.data.map((t) => t.id)).toEqual([recent.id, old.id]);
  });

  it('puts a trip that is under way in its own section first', () => {
    const now = trip('ongoing', '2026-10-06');
    const sections = groupTrips([trip('upcoming', '2026-12-01'), now]);
    expect(sections[0].key).toBe('ongoing');
    expect(sections[0].data[0].id).toBe(now.id);
  });

  it('returns nothing for no trips', () => {
    expect(groupTrips([])).toEqual([]);
  });
});

describe('historyTotals', () => {
  it('adds up spend and visited places across every trip', () => {
    const totals = historyTotals([
      trip('completed', '2026-08-01', { spend_total: 8000, items_visited: 9 }),
      trip('ongoing', '2026-10-06', { spend_total: 1500.5, items_visited: 2 }),
      trip('upcoming', '2026-12-01'),
    ]);
    expect(totals).toEqual({ trips: 3, completed: 1, spent: 9500.5, placesVisited: 11 });
  });
});

describe('phaseLabel', () => {
  it('uses plain-language labels', () => {
    expect(phaseLabel('undated')).toBe('Dates not set');
    expect(phaseLabel('completed')).toBe('Completed');
  });
});
