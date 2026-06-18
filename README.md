# ZSE Portfolio Monitor

Python Azure Functions backend and React dashboard for monitoring Zagrebacka burza (ZSE), tracking a personal stock portfolio, and generating buy/sell/hold recommendations.

## Recommended Free Hosting

Use GitHub Actions for scheduled monitoring and GitHub Pages for the dashboard.

1. Create a GitHub repository and push this project.
2. In the repository settings, add Actions secrets:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `OPENAI_API_KEY`
   - `PORTFOLIO_JSON`
   - `EXPERT_POSTS_JSON` (optional)
   - variable `EXPERT_FEED_URLS` (optional)
   - variable `DIVIDEND_TICKERS` (optional, comma-separated tickers)
3. Go to `Settings > Pages` and set source to `GitHub Actions`.
4. Run the `ZSE Monitor and Pages` workflow manually once from the `Actions` tab.

The workflow runs every 5 minutes during the relevant weekday UTC window, but `backend/run_monitor.py` only performs checks near the Zagreb market slots:

- 09:30 Europe/Zagreb local market check
- 15:30 Europe/Zagreb tactical check
- 17:00 Europe/Zagreb daily summary

The generated dashboard data is written to `frontend/public/data/portfolio.json` and published with the React app.
The published dashboard payload is sanitized: quantities, average buy prices, target prices, stop-loss values, and P&L are removed before publishing.

Example `PORTFOLIO_JSON` secret:

```json
[
  {
    "ticker": "KODT",
    "kolicina": 10,
    "prosjecna_kupovna_cijena": 1550.0,
    "broker_current_price": 1875.0,
    "broker_acquisition_value": 15500.0,
    "broker_market_value": 18750.0,
    "broker_profit_eur": 3250.0,
    "broker_return_pct": 20.97,
    "portfolio_weight_pct": 12.5
  }
]
```

Optional `EXPERT_POSTS_JSON` secret:

```json
[
  {
    "source": "Nenad Bakic Facebook",
    "title": "Objava o ZSE temi",
    "text": "Ovdje zalijepi tekst bitne javne objave.",
    "url": "https://www.facebook.com/nenad.bakic"
  }
]
```

Optional `EXPERT_FEED_URLS` repository variable accepts comma-separated RSS/feed URLs. Avoid storing Facebook login cookies or passwords in GitHub.

Optional dividend setup:

- Set repository variable `DIVIDEND_TICKERS` to a comma-separated list, for example `HT,ERNT,KOEI`.
- Or add `"has_dividend": true` and optionally `"dividend_yield_pct": 3.2` to a position in `PORTFOLIO_JSON`.

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
func start
```

Copy `backend/local.settings.sample.json` to `backend/local.settings.json` and fill secrets before local runs.

Timer logic runs Monday-Friday at:

- 09:30 Europe/Zagreb local market check
- 15:30 Europe/Zagreb tactical check
- 17:00 Europe/Zagreb daily summary

The Azure timer trigger wakes the function every minute during the relevant UTC window. The Python app then checks `Europe/Zagreb` local time before running a market check, so daylight saving time does not shift the intended local schedule.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` if you expose the backend HTTP endpoint from Azure or local Functions.
