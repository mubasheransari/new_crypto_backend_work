# Crypto Insights — Backend (FastAPI)

Backend for the Crypto Insights app: live market data, crypto news,
an education/knowledge base, user auth, a watchlist, AI-powered
chart-screenshot analysis (via Google Gemini), and an admin-managed
"Trade of the Day" feature.

## Features & data sources

| Feature | Source | API key needed? |
|---|---|---|
| Live prices, market cap, sparklines | CoinGecko public API | No (rate-limited) |
| Total market cap / global stats | CoinGecko public API | No |
| Crypto news | RSS feeds (Cointelegraph, Decrypt, BeInCrypto) by default; optionally CryptoCompare/CoinDesk if you set a key | No |
| Chart screenshot analysis | Google Gemini API | **Yes** |
| Trade of the Day | Posted via the built-in admin panel | No (uses your own admin key) |
| Education / TA knowledge base | Static content in `app/routers/education.py` | No |
| Auth + watchlist | Local SQLite DB | No |

## Setup

### Option A — Docker (recommended)

```bash
cd crypto_backend
cp .env.example .env
# edit .env: add GEMINI_API_KEY, CRYPTOCOMPARE_API_KEY, and set ADMIN_API_KEY

docker compose up --build
```

The API will be live at `http://localhost:8000`. Your SQLite database and
uploaded Trade of the Day images persist in `data/` and `uploads/` folders
created next to `docker-compose.yml`.

### Option B — Local Python venv

```bash
cd crypto_backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: add GEMINI_API_KEY, CRYPTOCOMPARE_API_KEY, and set ADMIN_API_KEY

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Key endpoints

- `POST /auth/register`, `POST /auth/login` — email/password auth, returns a JWT
- `GET /market/coins?page=1&per_page=50` — paginated live market list
- `GET /market/global` — total market cap, 24h change, BTC/ETH dominance
- `GET /market/coins/{id}` — coin detail
- `GET /news?category=BTC` — latest news, optional category filter (needs `CRYPTOCOMPARE_API_KEY`)
- `GET /education` / `GET /education/{slug}` — TA knowledge base
- `POST /analyzer/chart` — multipart upload (`file`, optional `coin_hint`, `note`) → structured AI analysis via Gemini
- `GET /watchlist` / `POST /watchlist` / `DELETE /watchlist/{coin_id}` — requires `Authorization: Bearer <token>`
- `GET /trade-of-day/latest`, `GET /trade-of-day` — public
- `POST /trade-of-day`, `DELETE /trade-of-day/{id}` — admin only (see `/admin` panel)

## The chart analyzer's response shape

```json
{
  "trend": "...",
  "key_pattern": "...",
  "current_price": "0.8051",
  "entry_price": "A pullback toward the 0.85-0.86 zone would offer a better-defined entry...",
  "stop_loss": "≈0.7424",
  "target_price": "≈1.00",
  "invalidation_level": "≈0.7424",
  "indicators": "...",
  "bullish_scenario": "...",
  "bearish_scenario": "...",
  "setup_clarity": "...",
  "risk_level": "High - primary trend is bearish and price sits near swing lows.",
  "volatility_read": "...",
  "disclaimer": "..."
}
```

Deliberate design choices worth knowing before you modify this:
- `current_price` is a plain readout; `entry_price` must reflect real
  technical reasoning, not just repeat `current_price`.
- Price fields only contain a specific number when Gemini can actually read
  it off the chart's axis labels - otherwise they say so plainly rather than
  guessing a fake-precise number.
- There is intentionally no numeric "success probability" / win-rate /
  confidence score anywhere in this schema, and `risk_level` is a word
  (Low/Medium/High) plus a real reason, never a number. No model can
  honestly compute a success probability from a chart screenshot, and
  fabricating one would be actively misleading for a tool people might
  trade real money against. See the docstring in
  `app/services/gemini_vision.py` before changing this.

## Trade of the Day & the admin panel

1. Set `ADMIN_API_KEY` in `.env` to any password you choose.
2. Open `http://localhost:8000/admin`, enter that key, fill in
   title/description/date-time, choose a chart image, and post.
3. It appears in the app's Trade tab (pull to refresh).

## Notes on the free/keyed data sources

**News** works out of the box with no signup at all - it pulls from public
RSS feeds (Cointelegraph, Decrypt, BeInCrypto). If you'd rather use
CryptoCompare/CoinDesk Data's news API instead, get a free key at
https://developers.coindesk.com/ and set it as `CRYPTOCOMPARE_API_KEY` -
it's used automatically when present, and if that request ever fails for
any reason, the app falls back to RSS automatically rather than showing
an error.

**CoinGecko's** public endpoint is rate-limited for anonymous use (roughly
10-30 requests/min); responses are cached for 30 seconds to help stay
under that.

**Gemini** models get retired from free-tier access or shut down outright
every few months. If the analyzer starts returning a `404 ... no longer
available` or `429 ... limit: 0` error mentioning a model name, check
https://ai.google.dev/gemini-api/docs/latest-model for the current
generally-available model and update `MODEL_NAME` in
`app/services/gemini_vision.py`.

## Swapping SQLite for Postgres

Set `DATABASE_URL` in `.env` to a Postgres connection string and add
`psycopg2-binary` to `requirements.txt` - no other code changes needed.
# -analyzer_app_backend
# new_crypto_backend_work
