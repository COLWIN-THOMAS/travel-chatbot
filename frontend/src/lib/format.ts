/** Indian digit grouping without relying on Intl (inconsistent across JS engines): 1234567 -> ₹12,34,567 */
export function inr(amount: number): string {
  const n = Math.round(Math.abs(amount));
  const s = String(n);
  let grouped = s;
  if (s.length > 3) {
    let head = s.slice(0, -3);
    const tail = s.slice(-3);
    const parts: string[] = [];
    while (head.length > 2) {
      parts.unshift(head.slice(-2));
      head = head.slice(0, -2);
    }
    if (head) parts.unshift(head);
    grouped = parts.join(',') + ',' + tail;
  }
  return (amount < 0 ? '-' : '') + '₹' + grouped;
}

export function clampPercent(p: number): number {
  if (!Number.isFinite(p)) return 0;
  return Math.max(0, Math.min(100, p));
}

/** green under 75%, amber up to the budget, red once over it */
export type BudgetTone = 'ok' | 'warn' | 'over';
export function budgetTone(percentUsed: number): BudgetTone {
  if (percentUsed > 100) return 'over';
  if (percentUsed >= 75) return 'warn';
  return 'ok';
}

const TIER_SYMBOLS: Record<string, string> = {
  Free: 'Free',
  Inexpensive: '₹',
  Moderate: '₹₹',
  Expensive: '₹₹₹',
  'Very Expensive': '₹₹₹₹',
};

export function priceTier(level: string | null | undefined): string {
  if (!level) return 'Price n/a';
  return TIER_SYMBOLS[level] ?? level;
}

export function isBudgetFriendly(level: string | null | undefined): boolean {
  return level === 'Free' || level === 'Inexpensive';
}

/** Parses a user-typed amount like "1,250.50" -> 1250.5. Returns null when not a positive number. */
export function parseAmount(text: string): number | null {
  const cleaned = text.replace(/[,\s₹]/g, '');
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return null;
  const v = Number(cleaned);
  return v > 0 && v < 10_000_000 ? v : null;
}
