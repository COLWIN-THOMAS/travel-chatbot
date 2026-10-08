import type { TripPhase, TripSummary } from './types';

export interface HistorySection {
  key: 'ongoing' | 'upcoming' | 'past';
  title: string;
  data: TripSummary[];
}

const byStartAsc = (a: TripSummary, b: TripSummary) => (a.start_date ?? '').localeCompare(b.start_date ?? '');
const byStartDesc = (a: TripSummary, b: TripSummary) => (b.start_date ?? '').localeCompare(a.start_date ?? '');
const byCreatedDesc = (a: TripSummary, b: TripSummary) => b.created_at.localeCompare(a.created_at);

/**
 * Splits the user's trips into what is happening now, what is coming up (dated trips by date, then trips with
 * no dates yet), and past trips - the trip history - most recent first. Empty sections are dropped.
 */
export function groupTrips(trips: TripSummary[]): HistorySection[] {
  const ongoing = trips.filter((t) => t.phase === 'ongoing').sort(byStartAsc);
  const dated = trips.filter((t) => t.phase === 'upcoming').sort(byStartAsc);
  const undated = trips.filter((t) => t.phase === 'undated').sort(byCreatedDesc);
  const past = trips.filter((t) => t.phase === 'completed').sort(byStartDesc);
  const sections: HistorySection[] = [
    { key: 'ongoing', title: 'Happening now', data: ongoing },
    { key: 'upcoming', title: 'Upcoming', data: [...dated, ...undated] },
    { key: 'past', title: 'Past trips', data: past },
  ];
  return sections.filter((s) => s.data.length > 0);
}

export interface HistoryTotals {
  trips: number;
  completed: number;
  spent: number;
  placesVisited: number;
}

/** Headline numbers for the history screen: everything spent and visited across all trips. */
export function historyTotals(trips: TripSummary[]): HistoryTotals {
  return {
    trips: trips.length,
    completed: trips.filter((t) => t.phase === 'completed').length,
    spent: trips.reduce((sum, t) => sum + t.spend_total, 0),
    placesVisited: trips.reduce((sum, t) => sum + t.items_visited, 0),
  };
}

const PHASE_LABEL: Record<TripPhase, string> = {
  ongoing: 'Happening now', upcoming: 'Upcoming', completed: 'Completed', undated: 'Dates not set',
};
export const phaseLabel = (p: TripPhase) => PHASE_LABEL[p];

