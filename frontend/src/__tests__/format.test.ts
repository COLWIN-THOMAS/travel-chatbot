import { budgetTone, clampPercent, inr, isBudgetFriendly, parseAmount, priceTier } from '../lib/format';

describe('inr', () => {
  it('uses Indian digit grouping', () => {
    expect(inr(0)).toBe('₹0');
    expect(inr(999)).toBe('₹999');
    expect(inr(1000)).toBe('₹1,000');
    expect(inr(15000)).toBe('₹15,000');
    expect(inr(150000)).toBe('₹1,50,000');
    expect(inr(12345678)).toBe('₹1,23,45,678');
  });
  it('rounds and handles negatives', () => {
    expect(inr(1234.6)).toBe('₹1,235');
    expect(inr(-2500)).toBe('-₹2,500');
  });
});

describe('budgetTone', () => {
  it('is green under 75, amber up to 100, red beyond', () => {
    expect(budgetTone(0)).toBe('ok');
    expect(budgetTone(74.9)).toBe('ok');
    expect(budgetTone(75)).toBe('warn');
    expect(budgetTone(100)).toBe('warn');
    expect(budgetTone(100.1)).toBe('over');
  });
});

describe('clampPercent', () => {
  it('bounds and sanitises', () => {
    expect(clampPercent(-5)).toBe(0);
    expect(clampPercent(250)).toBe(100);
    expect(clampPercent(NaN)).toBe(0);
    expect(clampPercent(42)).toBe(42);
  });
});

describe('parseAmount', () => {
  it('accepts plain, comma and rupee-prefixed numbers', () => {
    expect(parseAmount('250')).toBe(250);
    expect(parseAmount('1,250.50')).toBe(1250.5);
    expect(parseAmount('₹ 300')).toBe(300);
  });
  it('rejects zero, negatives, junk and absurd values', () => {
    for (const bad of ['', '0', '-5', 'abc', '12.345', '1e3', '99999999']) expect(parseAmount(bad)).toBeNull();
  });
});

describe('price tiers', () => {
  it('maps Google tiers to symbols and flags budget-friendly ones', () => {
    expect(priceTier('Moderate')).toBe('₹₹');
    expect(priceTier(null)).toBe('Price n/a');
    expect(isBudgetFriendly('Inexpensive')).toBe(true);
    expect(isBudgetFriendly('Free')).toBe(true);
    expect(isBudgetFriendly('Expensive')).toBe(false);
    expect(isBudgetFriendly(null)).toBe(false);
  });
});
