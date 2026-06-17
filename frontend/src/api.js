const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function fetchPortfolio() {
  if (!API_BASE_URL) {
    const response = await fetch("./data/portfolio.json", { cache: "no-store" });
    if (!response.ok) {
      return mockPortfolio;
    }
    const payload = await response.json();
    return payload.positions?.length ? payload.positions : mockPortfolio;
  }

  const response = await fetch(`${API_BASE_URL.replace(/\/$/, "")}/api/portfolio`);
  if (!response.ok) {
    throw new Error(`Portfolio API returned ${response.status}`);
  }
  return response.json();
}

const mockPortfolio = [
  {
    ticker: "KODT",
    quantity: 10,
    average_buy_price: 1550,
    target_price: 1900,
    stop_loss: 1350,
    investment_horizon: "long_term",
    quote: { ticker: "KODT", last_price: 1875, change_pct: 2.1, turnover_eur: 38500 },
    technical: { rsi: 64.2, ma50: 1740, trend: "uptrend", status: "RSI 64.2, cijena iznad MA50" },
    sentiment: { sentiment: "bullish", summary: "Rasprava je mirno pozitivna uz fokus na narudžbe i stabilnu dobit." },
    recommendation: { action: "ZADRŽI DUGOROČNO", reason: "Dugoročni horizont ignorira kratkoročni šum.", urgent: false },
    pnl_eur: 3250,
    pnl_pct: 20.97,
    wow_event: false,
    checked_at: new Date().toISOString(),
  },
  {
    ticker: "SPAN",
    quantity: 35,
    average_buy_price: 48,
    target_price: 62,
    stop_loss: 41,
    investment_horizon: "short_term",
    quote: { ticker: "SPAN", last_price: 63.4, change_pct: 4.6, turnover_eur: 52200 },
    technical: { rsi: 73.4, ma50: 57.8, trend: "uptrend", status: "RSI 73.4, cijena iznad MA50" },
    sentiment: { sentiment: "neutral", summary: "Forum bilježi pojačan interes bez jasne panike." },
    recommendation: { action: "PRODAJ", reason: "Cijena je probila kratkoročni target.", urgent: true },
    pnl_eur: 539,
    pnl_pct: 32.08,
    wow_event: true,
    checked_at: new Date().toISOString(),
  },
  {
    ticker: "HT",
    quantity: 120,
    average_buy_price: 27.5,
    target_price: 34,
    stop_loss: 23.5,
    investment_horizon: "long_term",
    quote: { ticker: "HT", last_price: 31.2, change_pct: -0.3, turnover_eur: 19000 },
    technical: { rsi: 48.5, ma50: 30.9, trend: "sideways", status: "RSI 48.5, blizu MA50" },
    sentiment: { sentiment: "neutral", summary: "Komentari su umjereni i bez važnih negativnih novosti." },
    recommendation: { action: "ZADRŽI DUGOROČNO", reason: "Dugoročni horizont ignorira kratkoročni šum.", urgent: false },
    pnl_eur: 444,
    pnl_pct: 13.45,
    wow_event: false,
    checked_at: new Date().toISOString(),
  },
];
