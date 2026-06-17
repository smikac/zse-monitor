import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, RefreshCw, TrendingDown, TrendingUp } from "lucide-react";
import { fetchPortfolio } from "./api.js";

export default function Dashboard() {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadPortfolio() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchPortfolio();
      setPositions(data);
    } catch (err) {
      setError("Nije moguće dohvatiti portfelj. Prikaz provjeri nakon dostupnosti API-ja.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPortfolio();
  }, []);

  const alerts = useMemo(
    () => positions.filter((item) => item.recommendation?.urgent || item.recommendation?.action?.includes("PRODAJ")),
    [positions],
  );

  return (
    <main className="dashboard">
      <header className="topbar">
        <div>
          <p className="eyebrow">Zagrebačka burza</p>
          <h1>Portfelj i signali</h1>
        </div>
        <button className="iconButton" onClick={loadPortfolio} disabled={loading} aria-label="Osvježi podatke">
          <RefreshCw size={18} />
          <span>{loading ? "Osvježavam" : "Osvježi"}</span>
        </button>
      </header>

      {error && <div className="notice">{error}</div>}

      <section className="alertGrid" aria-label="Hitni alarmi">
        {alerts.length === 0 ? (
          <div className="emptyAlert">
            <AlertTriangle size={20} />
            <span>Nema hitnih prodajnih alarma.</span>
          </div>
        ) : (
          alerts.map((item) => <AlertCard key={item.ticker} item={item} />)
        )}
      </section>

      <section className="tableShell">
        <div className="sectionHeader">
          <h2>Pregled portfelja</h2>
          <span>{positions.length} pozicije</span>
        </div>
        <PortfolioTable positions={positions} loading={loading} />
      </section>
    </main>
  );
}

function AlertCard({ item }) {
  return (
    <article className="alertCard">
      <div className="alertTitle">
        <AlertTriangle size={20} />
        <strong>{item.ticker}</strong>
      </div>
      <div className="alertAction">{item.recommendation.action}</div>
      <p>{item.recommendation.reason}</p>
      <div className="metricRow">
        <span>{formatCurrency(item.quote?.last_price)}</span>
        <span className={item.quote?.change_pct >= 0 ? "positive" : "negative"}>
          {formatPercent(item.quote?.change_pct)}
        </span>
      </div>
    </article>
  );
}

function PortfolioTable({ positions, loading }) {
  if (loading && positions.length === 0) {
    return <div className="tableState">Učitavanje tržišnih podataka...</div>;
  }

  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Cijena</th>
            <th>P&L</th>
            <th>Tehnika</th>
            <th>AI sažetak</th>
            <th>Zadnja provjera</th>
            <th>Preporuka</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((item) => (
            <tr key={item.ticker}>
              <td>
                <div className="tickerCell">
                  <strong>{item.ticker}</strong>
                  <span>{item.quantity} kom · {item.investment_horizon === "long_term" ? "dugo" : "kratko"}</span>
                </div>
              </td>
              <td>
                <strong>{formatCurrency(item.quote?.last_price)}</strong>
                <span className={item.quote?.change_pct >= 0 ? "positive inline" : "negative inline"}>
                  {item.quote?.change_pct >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                  {formatPercent(item.quote?.change_pct)}
                </span>
              </td>
              <td className={item.pnl_eur >= 0 ? "positive" : "negative"}>
                {formatCurrency(item.pnl_eur)}
                <span className="subtle">{formatPercent(item.pnl_pct)}</span>
              </td>
              <td>
                <Badge tone={technicalTone(item.technical?.trend)}>{item.technical?.status ?? "N/A"}</Badge>
              </td>
              <td className="summaryCell">{item.sentiment?.summary ?? "N/A"}</td>
              <td>{formatDateTime(item.checked_at)}</td>
              <td>
                <Badge tone={recommendationTone(item.recommendation?.action)}>{item.recommendation?.action ?? "N/A"}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Badge({ children, tone }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

function recommendationTone(action = "") {
  if (action.includes("PRODAJ")) return "danger";
  if (action.includes("KUPI")) return "success";
  return "neutral";
}

function technicalTone(trend = "") {
  if (trend === "uptrend") return "success";
  if (trend === "downtrend") return "danger";
  return "neutral";
}

function formatCurrency(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return new Intl.NumberFormat("hr-HR", { style: "currency", currency: "EUR" }).format(value);
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatDateTime(value) {
  if (!value) return "N/A";
  return new Intl.DateTimeFormat("hr-HR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
