export function formatCurrency(
  amount: number,
  currency = "USD",
  options: Intl.NumberFormatOptions = {},
  locale?: string,
): string {
  const normalizedCurrency = currency.trim().toUpperCase() || "USD";
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: normalizedCurrency,
      maximumFractionDigits: 2,
      ...options,
    }).format(Number.isFinite(amount) ? amount : 0);
  } catch {
    return `${normalizedCurrency} ${(Number.isFinite(amount) ? amount : 0).toLocaleString(locale)}`;
  }
}
