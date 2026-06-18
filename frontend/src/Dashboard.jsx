import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, RefreshCw, TrendingDown, TrendingUp } from "lucide-react";
import { fetchPortfolio } from "./api.js";

const WORKFLOW_URL = "https://github.com/smikac/zse-monitor/actions/workflows/zse-monitor-pages.yml";

export default function Dashboard() {
  const [meta, setMeta] = useState({});
  const [positions, setPositions] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [forumSignals, setForumSignals] = useState([]);
  const [expertSignals, setExpertSignals] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [forecastItem, setForecastItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadPortfolio() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchPortfolio();
      setMeta(data.meta ?? {});
      setPositions(data.positions);
      setOpportunities(data.opportunities);
      setForumSignals(data.forumSignals);
      setExpertSignals(data.expertSignals);
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

  async function checkNow() {
    await loadPortfolio();
    setModalOpen(true);
  }

  async function refreshView() {
    await loadPortfolio();
  }

  return (
    <main className="dashboard">
      <header className="topbar">
        <div>
          <p className="eyebrow">Zagrebačka burza</p>
          <h1>Portfelj i signali</h1>
          <p className="lastCheck">Zadnja provjera: <strong>{formatDateTime(meta.generated_at)}</strong></p>
        </div>
        <div className="topbarActions">
          <button className="iconButton" onClick={refreshView} disabled={loading} aria-label="Osvježi prikaz">
            <RefreshCw size={18} />
            <span>{loading ? "Osvježavam" : "Osvježi prikaz"}</span>
          </button>
          <button className="iconButton" onClick={checkNow} disabled={loading} aria-label="Provjeri stanje">
            <AlertTriangle size={18} />
            <span>Provjeri stanje</span>
          </button>
          <a className="iconButton linkButton" href={WORKFLOW_URL} target="_blank" rel="noreferrer" title="Otvara GitHub Actions gdje ručno pokrećeš novi run. Statički GitHub Pages ne smije čuvati GitHub token u browseru.">
            Pokreni u Actions
          </a>
        </div>
      </header>

      {error && <div className="notice">{error}</div>}

      <section className="alertGrid" aria-label="Hitni alarmi">
        {positions.length === 0 ? (
          <div className="emptyAlert">
            <AlertTriangle size={20} />
            <span>Nema objavljenih portfolio podataka. Pokreni workflow nakon dodavanja PORTFOLIO_JSON secreta.</span>
          </div>
        ) : alerts.length === 0 ? (
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
        <PortfolioTable positions={positions} loading={loading} onSelect={setForecastItem} />
      </section>

      <section className="tableShell secondaryShell">
        <div className="sectionHeader">
          <h2>Dnevni ZSE kandidati</h2>
          <span>{opportunities.length} signali · najbolje kupnje prvo</span>
        </div>
        <OpportunityTable opportunities={opportunities} loading={loading} onSelect={setForecastItem} />
      </section>

      {forecastItem && <ForecastModal item={forecastItem} onClose={() => setForecastItem(null)} />}

      {modalOpen && (
        <StatusModal
          alerts={alerts}
          opportunities={opportunities}
          forumSignals={forumSignals}
          expertSignals={expertSignals}
          onClose={() => setModalOpen(false)}
        />
      )}
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

function PortfolioTable({ positions, loading, onSelect }) {
  if (loading && positions.length === 0) {
    return <div className="tableState">Učitavanje tržišnih podataka...</div>;
  }

  if (positions.length === 0) {
    return <div className="tableState">Nema podataka za prikaz.</div>;
  }

  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Cijena</th>
            <th>Dividenda</th>
            <th>Tehnika</th>
            <th>AI sažetak</th>
            <th>Zadnja provjera</th>
            <th>Preporuka</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((item) => (
            <tr key={item.ticker} className={`${rowSignalClass(item.recommendation?.action)} clickableRow`} onClick={() => onSelect(item)}>
              <td>
                <div className="tickerCell">
                  <strong>{item.ticker}</strong>
                  <span>{formatPositionMeta(item)}</span>
                </div>
              </td>
              <td>
                <strong>{formatCurrency(item.quote?.last_price)}</strong>
                <span className={item.quote?.change_pct >= 0 ? "positive inline" : "negative inline"}>
                  {item.quote?.change_pct >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                  {formatPercent(item.quote?.change_pct)}
                </span>
              </td>
              <td><DividendCell item={item} /></td>
              <td>
                <Badge tone={technicalTone(item.technical?.trend)}>{item.technical?.status ?? "N/A"}</Badge>
              </td>
              <td className="summaryCell">{item.sentiment?.summary ?? "N/A"}</td>
              <td>{formatDateTime(item.checked_at)}</td>
              <td>
                <Badge tone={recommendationTone(item.recommendation?.action)}>{item.recommendation?.action ?? "N/A"}</Badge>
                <span className="subtle">{item.horizon_reason}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OpportunityTable({ opportunities, loading, onSelect }) {
  if (loading && opportunities.length === 0) {
    return <div className="tableState">Učitavanje ZSE kandidata...</div>;
  }

  if (opportunities.length === 0) {
    return <div className="tableState">Nema dovoljno jakih ZSE signala izvan portfelja.</div>;
  }

  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Cijena</th>
            <th>Dividenda</th>
            <th>Promet</th>
            <th>Tehnika</th>
            <th>Signal</th>
            <th>Razlog</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item) => (
            <tr key={item.ticker} className={`${opportunityRowClass(item.action)} clickableRow`} onClick={() => onSelect(item)}>
              <td><strong>{item.ticker}</strong></td>
              <td>
                <strong>{formatCurrency(item.quote?.last_price)}</strong>
                <span className={item.quote?.change_pct >= 0 ? "positive inline" : "negative inline"}>
                  {item.quote?.change_pct >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                  {formatPercent(item.quote?.change_pct)}
                </span>
              </td>
              <td><DividendCell item={item} /></td>
              <td>{formatCurrency(item.quote?.turnover_eur)}</td>
              <td><Badge tone={technicalTone(item.technical?.trend)}>{item.technical?.status ?? "N/A"}</Badge></td>
              <td><Badge tone={opportunityTone(item.action)}>{item.action}</Badge></td>
              <td className="summaryCell">{item.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DividendCell({ item }) {
  if (!item.has_dividend) {
    return (
      <div className="dividendCell empty">
        <input className="dividendCheck" type="checkbox" checked={false} readOnly aria-label="Nema dividendu" />
        <span>Nema</span>
      </div>
    );
  }

  const amount = item.dividend_per_share
    ? `${formatNumber(item.dividend_per_share)} ${item.dividend_currency ?? "EUR"}`
    : "Da";
  const details = [
    item.dividend_yield_pct ? `${formatNumber(item.dividend_yield_pct)}%` : null,
    item.dividend_payment_date ? `isplata ${formatDate(item.dividend_payment_date)}` : null,
  ].filter(Boolean).join(" · ");

  return (
    <div className="dividendCell">
      <input className="dividendCheck" type="checkbox" checked readOnly aria-label="Ima dividendu" />
      <span>
        <strong>{amount}</strong>
        {details && <small>{details}</small>}
      </span>
    </div>
  );
}

function ForecastModal({ item, onClose }) {
  const forecast = item.annual_forecast;
  return (
    <div className="modalBackdrop" role="presentation" onClick={onClose}>
      <section className="modalPanel forecastPanel" role="dialog" aria-modal="true" aria-label="Jednogodišnja prognoza" onClick={(event) => event.stopPropagation()}>
        <div className="modalHeader">
          <h2>{item.ticker} prognoza</h2>
          <button className="closeButton" onClick={onClose} aria-label="Zatvori">x</button>
        </div>
        <div className="forecastBody">
          <div className={`forecastHero ${forecastTone(forecast?.direction)}`}>
            <span>12 mjeseci</span>
            <strong>{forecast?.direction ?? "NEUTRALNO"}</strong>
            <small>Pouzdanost {Math.round((forecast?.confidence ?? 0) * 100)}%</small>
          </div>
          <p>{forecast?.summary ?? "Nema dovoljno podataka za prognozu."}</p>
          <div className="forecastMetrics">
            <span>Cijena: <strong>{formatCurrency(item.quote?.last_price)}</strong></span>
            <span>Promjena: <strong>{formatPercent(item.quote?.change_pct)}</strong></span>
            <span>Dividenda: <strong>{formatDividendSummary(item)}</strong></span>
          </div>
          {forecast?.drivers?.length > 0 && (
            <div className="signalGroup compactGroup">
              <h3>Zašto</h3>
              <ul className="driverList">
                {forecast.drivers.map((driver) => <li key={driver}>{driver}</li>)}
              </ul>
            </div>
          )}
          <p className="forecastDisclaimer">Ovo je heuristička procjena iz dostupnih tržišnih signala, ne financijski savjet.</p>
        </div>
      </section>
    </div>
  );
}

function StatusModal({ alerts, opportunities, forumSignals, expertSignals, onClose }) {
  const buyIdeas = opportunities.filter((item) => item.action === "KUPI");
  const relevantForumSignals = forumSignals.filter((item) => item.action === "KUPI" || item.action === "PRODAJ");
  const relevantExpertSignals = expertSignals.filter((item) => item.action === "KUPI" || item.action === "PRODAJ");
  const hasSignals = alerts.length > 0 || buyIdeas.length > 0 || relevantForumSignals.length > 0 || relevantExpertSignals.length > 0;

  return (
    <div className="modalBackdrop" role="presentation" onClick={onClose}>
      <section className="modalPanel" role="dialog" aria-modal="true" aria-label="Provjera stanja" onClick={(event) => event.stopPropagation()}>
        <div className="modalHeader">
          <h2>Provjera stanja</h2>
          <button className="closeButton" onClick={onClose} aria-label="Zatvori">x</button>
        </div>

        {!hasSignals && <p className="modalEmpty">Nema hitnih prodaja, jakih kupovnih kandidata ni bitnih forum signala.</p>}

        {alerts.length > 0 && (
          <SignalGroup title="Hitno prodati">
            {alerts.map((item) => (
              <SignalItem
                key={item.ticker}
                tone="danger"
                title={`${item.ticker} · ${item.recommendation.action}`}
                meta={`${formatCurrency(item.quote?.last_price)} · ${formatPercent(item.quote?.change_pct)}`}
                text={item.recommendation.reason}
              />
            ))}
          </SignalGroup>
        )}

        {buyIdeas.length > 0 && (
          <SignalGroup title="Zanimljivo za kupiti">
            {buyIdeas.slice(0, 6).map((item) => (
              <SignalItem
                key={item.ticker}
                tone="success"
                title={`${item.ticker} · ${item.action}`}
                meta={`${formatCurrency(item.quote?.last_price)} · ${formatPercent(item.quote?.change_pct)} · promet ${formatCurrency(item.quote?.turnover_eur)}`}
                text={item.reason}
              />
            ))}
          </SignalGroup>
        )}

        {relevantForumSignals.length > 0 && (
          <SignalGroup title="Forum signali">
            {relevantForumSignals.slice(0, 6).map((item) => (
              <SignalItem
                key={`${item.ticker}-${item.source_url}`}
                tone={item.action === "PRODAJ" ? "danger" : "success"}
                title={`${item.ticker} · ${item.action}`}
                meta={`pouzdanost ${Math.round((item.confidence ?? 0) * 100)}%`}
                text={item.summary}
              />
            ))}
          </SignalGroup>
        )}

        {relevantExpertSignals.length > 0 && (
          <SignalGroup title="Expert komentari">
            {relevantExpertSignals.slice(0, 6).map((item) => (
              <SignalItem
                key={`${item.ticker}-${item.source_url}`}
                tone={item.action === "PRODAJ" ? "danger" : "success"}
                title={`${item.ticker} · ${item.action}`}
                meta={`pouzdanost ${Math.round((item.confidence ?? 0) * 100)}%`}
                text={item.summary}
              />
            ))}
          </SignalGroup>
        )}
      </section>
    </div>
  );
}

function SignalGroup({ title, children }) {
  return (
    <div className="signalGroup">
      <h3>{title}</h3>
      <div className="signalList">{children}</div>
    </div>
  );
}

function SignalItem({ tone, title, meta, text }) {
  return (
    <article className={`signalItem ${tone}`}>
      <strong>{title}</strong>
      <span>{meta}</span>
      <p>{text}</p>
    </article>
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

function opportunityTone(action = "") {
  if (action === "KUPI") return "success";
  if (action === "IZBJEGNI") return "danger";
  return "neutral";
}

function rowSignalClass(action = "") {
  if (action.includes("PRODAJ")) return "sellRow";
  if (action.includes("KUPI")) return "buyRow";
  return "";
}

function opportunityRowClass(action = "") {
  if (action === "KUPI") return "buyRow";
  if (action === "IZBJEGNI") return "sellRow";
  return "";
}

function forecastTone(direction = "") {
  if (direction === "RAST") return "success";
  if (direction === "PAD") return "danger";
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

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return new Intl.NumberFormat("hr-HR", { maximumFractionDigits: 2 }).format(value);
}

function formatDate(value) {
  if (!value) return "N/A";
  return new Intl.DateTimeFormat("hr-HR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
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

function formatDividendSummary(item) {
  if (!item.has_dividend) return "ne";
  if (!item.dividend_per_share) return "da";
  const yieldText = item.dividend_yield_pct ? ` (${formatNumber(item.dividend_yield_pct)}%)` : "";
  return `${formatNumber(item.dividend_per_share)} ${item.dividend_currency ?? "EUR"}${yieldText}`;
}

function formatPositionMeta(item) {
  const horizon = item.investment_horizon === "long_term" ? "dugo" : "kratko";
  if (item.quantity === null || item.quantity === undefined) {
    return `privatno · ${horizon}`;
  }
  return `${item.quantity} kom · ${horizon}`;
}
