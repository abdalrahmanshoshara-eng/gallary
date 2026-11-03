/**
 * USD amounts. The backend sends money as decimal strings ("1250.00") — never floats.
 * Latin digits for prices (ADR-04, pending final confirmation).
 */
const usd = new Intl.NumberFormat("ar-SY-u-nu-latn", {
  style: "currency",
  currency: "USD",
  currencyDisplay: "narrowSymbol",
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatUsd(amount: string | number): string {
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (!Number.isFinite(value)) throw new RangeError(`invalid amount: ${String(amount)}`);
  return usd.format(value);
}
