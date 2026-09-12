// Shared currency-aware formatting for every Finance/Invoice/Wallet
// surface — invoices can be billed in USD or PKR (see backend Finance
// Settings), so a hardcoded "$" prefix is wrong once PKR is in play.
export function formatMoney(amount: number, currency: string = "USD") {
  const sign = amount < 0 ? "-" : "";
  const abs = Math.abs(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (currency === "USD") return `${sign}$${abs}`;
  return `${sign}${currency} ${abs}`;
}

export function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
