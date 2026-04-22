# AiTradingBot

An AI-powered news-driven trading system for the Indian stock market (NSE). Fetches live financial news from GNews, analyzes sentiment using Google Gemini AI, generates trading signals through a rule-based engine, and executes orders via Zerodha's Kite Connect API.

> **Disclaimer:** This project is for **educational purposes only**. Real trading involves significant financial risk. Always test thoroughly with paper trading before considering live deployment. Ensure compliance with SEBI regulations and Zerodha's terms of service.

---

## How It Works

```
GNews API  -->  Gemini AI  -->  Signal Engine  -->  Zerodha Kite
(fetch news)    (sentiment)     (BUY/SELL/HOLD)    (execute orders)
```

1. **Fetch News** — Pulls live financial headlines from GNews API (Indian business news)
2. **Ticker Detection** — Identifies NSE stock tickers mentioned in articles (RELIANCE, TCS, INFY, etc.)
3. **RAG Context** — Retrieves relevant company context using FAISS vector store
4. **Gemini Analysis** — Sends article + context to Google Gemini for structured sentiment analysis (impact score, confidence, severity, event type)
5. **Signal Generation** — Rule-based engine converts analysis into BUY/SELL/HOLD signals with strength scores
6. **Order Execution** — Executes signals via Zerodha Kite Connect (paper or live mode)
7. **Dashboard** — Real-time web dashboard shows signals, news feed, and ticker states

---

## Features

- **Live News Ingestion** — Fetches Indian market news from GNews API with deduplication
- **AI Sentiment Analysis** — Google Gemini analyzes news impact with structured JSON output (event type, impact score, confidence, risk flags)
- **Rule-Based Signal Engine** — Transparent, deterministic BUY/SELL/HOLD signals with full reasoning
- **Zerodha Integration** — Live order execution via Kite Connect with paper trading mode
- **State Management** — Tracks company state with conflict resolution and event history
- **RAG Retrieval** — FAISS-based vector store for contextual analysis
- **Web Dashboard** — Real-time monitoring of signals, news, analyses, and ticker states
- **Audit Trail** — Full traceability of every analysis with citations
- **Indian Market Support** — 30+ NSE stock ticker aliases (Reliance, TCS, HDFC Bank, etc.)

---

## Tech Stack

| Category | Technologies |
|---|---|
| **Core** | Python 3.11+, FastAPI, Uvicorn |
| **AI/LLM** | Google Gemini (via `google-genai` SDK) |
| **News** | GNews API |
| **Broker** | Zerodha Kite Connect |
| **Database** | SQLite |
| **Vector Store** | FAISS (in-memory with DB fallback) |
| **Models** | Pydantic v2 |
| **Testing** | pytest, pytest-asyncio |

---

## Project Structure

```
AiTradingBot/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app + all endpoints
│   ├── models.py               # Pydantic schemas
│   ├── db.py                   # SQLite operations
│   ├── gnews_fetcher.py        # GNews API integration
│   ├── llm_analyzer.py         # Gemini LLM provider + stub
│   ├── zerodha_executor.py     # Kite Connect order execution
│   ├── signal_engine.py        # Rule-based signal generation
│   ├── state_manager.py        # Company state management
│   ├── ingest.py               # News ingestion + dedup
│   ├── ticker_linker.py        # Ticker extraction (US + NSE)
│   ├── rag.py                  # FAISS vector store
│   ├── utils.py                # Utility functions
│   └── templates/
│       └── dashboard.html      # Web dashboard
├── tests/
│   ├── test_state_merge.py     # State merge tests
│   └── test_pipeline.py        # E2E pipeline tests
├── data/
│   ├── sample_data.py          # Mock news data
│   └── trading_bot.db          # SQLite database (auto-created)
├── run_pipeline.py             # Standalone E2E pipeline script
├── demo.py                     # Demo with sample data
├── fake_data_sender.py         # Test harness with fake news
├── requirements.txt
├── pyproject.toml
├── .env                        # API keys (not committed)
├── .gitignore
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- [GNews API key](https://gnews.io/) (free tier available)
- [Google Gemini API key](https://ai.google.dev/) (free tier available)
- [Zerodha Kite Connect](https://kite.trade/) subscription (optional for paper trading)

### Installation

```bash
git clone https://github.com/SiniDevelops/AiTradingBot.git
cd AiTradingBot
python -m venv venv
venv\Scripts\activate        # On Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
# Required for news fetching
GNEWS_API_KEY=your_gnews_api_key

# Required for AI sentiment analysis
GEMINI_API_KEY=your_gemini_api_key

# Required for live trading (optional for paper mode)
KITE_API_KEY=your_kite_api_key
KITE_API_SECRET=your_kite_api_secret
KITE_REQUEST_TOKEN=your_kite_request_token

# Trading mode: paper (default) or live
TRADING_MODE=paper
```

| Variable | Required | Description |
|---|---|---|
| `GNEWS_API_KEY` | Yes | GNews API key for fetching news |
| `GEMINI_API_KEY` | Yes | Google Gemini API key for sentiment analysis |
| `KITE_API_KEY` | For live trading | Zerodha API key |
| `KITE_API_SECRET` | For live trading | Zerodha API secret |
| `KITE_REQUEST_TOKEN` | For live trading | OAuth request token (expires after one use) |
| `TRADING_MODE` | No | `paper` (default) or `live` |
| `MAX_CAPITAL_PER_TRADE` | No | Max capital per trade (default: 10,000) |
| `DAILY_LOSS_LIMIT` | No | Daily loss limit (default: 3,000) |

---

## Usage

### Quick Test — Run the Full Pipeline

The fastest way to test everything end-to-end:

```bash
python run_pipeline.py --max-articles 5
```

This will:
1. Fetch 5 news articles from GNews
2. Detect stock tickers (RELIANCE, TCS, INFY, etc.)
3. Analyze each with Gemini AI
4. Generate BUY/SELL/HOLD signals
5. Execute via Zerodha (paper mode by default)

You can also search for specific stocks:

```bash
python run_pipeline.py --query "Reliance Industries" "Infosys earnings" --max-articles 3
```

### Start the Web Server & Dashboard

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open in your browser:
- **Dashboard**: http://127.0.0.1:8000/dashboard
- **API Docs**: http://127.0.0.1:8000/docs

### Trigger Pipeline via API

With the server running, trigger the full pipeline:

```bash
curl -X POST "http://127.0.0.1:8000/fetch_and_analyze?max_articles=5"
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/fetch_and_analyze` | Full pipeline: GNews -> Gemini -> Signal -> Execute |
| `POST` | `/ingest_news` | Ingest a single news article |
| `POST` | `/analyze_news/{news_id}` | Analyze an ingested article |
| `POST` | `/batch_analyze` | Ingest and analyze multiple articles |
| `GET` | `/signals` | Get all recent trading signals |
| `GET` | `/signals/{ticker}` | Get signals for a specific ticker |
| `GET` | `/executions` | Get all order executions |
| `GET` | `/state/{ticker}` | Get current state for a ticker |
| `GET` | `/events/{ticker}` | Get event history for a ticker |
| `GET` | `/audit/{audit_id}` | Get audit record of an analysis |
| `GET` | `/dashboard` | Web dashboard |
| `GET` | `/health` | Health check |

---

## Signal Engine

The signal engine uses transparent, deterministic rules to convert Gemini's analysis into trading signals:

### Signal Flow

```
Gemini Analysis -> Quality Gates -> Impact Score -> Direction -> Strength
```

### Thresholds

| Parameter | Value | Description |
|---|---|---|
| BUY threshold | impact > +0.3 | Positive news triggers BUY |
| SELL threshold | impact < -0.3 | Negative news triggers SELL |
| Min confidence | 0.6 | Below this, always HOLD |
| Strong signal | \|impact\| > 0.6 | Marked as STRONG |

### Blocking Conditions (force HOLD)

- Risk flags: `rumor`, `low_quality_source`
- Contradiction flags: `conflicts_with_guidance`, `conflicts_with_state`
- Low confidence (below 0.6)

Every signal includes explicit **reasons** explaining why it was generated.

---

## Supported Tickers

### Indian Market (NSE)
RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, WIPRO, BHARTIARTL, ITC, SBIN, HINDUNILVR, BAJFINANCE, KOTAKBANK, LT, MARUTI, ASIANPAINT, TITAN, SUNPHARMA, TATAMOTORS, TATASTEEL, POWERGRID, NTPC, ADANIENT, ADANIPORTS, HCLTECH, TECHM, AXISBANK, INDUSINDBK

### US Market
AAPL, MSFT, TSLA, META, AMZN, GOOGL, NVDA

---

## Zerodha Authentication

Kite Connect uses a browser-based OAuth flow:

1. Get your `api_key` and `api_secret` from [Kite Connect Developer Console](https://developers.kite.trade)
2. Visit `https://kite.zerodha.com/connect/login?v=3&api_key=YOUR_API_KEY`
3. Log in and copy the `request_token` from the redirect URL
4. Set it in `.env` as `KITE_REQUEST_TOKEN`

> **Note:** The `request_token` expires after one use. The bot exchanges it for an `access_token` on startup. If auth fails, the bot continues in **log-only mode** (signals are generated but not executed).

---

## Database

SQLite database at `data/trading_bot.db` with these tables:

| Table | Purpose |
|---|---|
| `news_raw` | Raw article storage |
| `news_clean` | Deduplicated articles with tickers |
| `ticker_profile` | Long-term company profiles |
| `state_events` | Append-only event history |
| `state_snapshot` | Current state snapshots (JSON) |
| `vector_chunks` | Vector embeddings metadata |
| `analysis_runs` | Audit trail (inputs/outputs/citations) |
| `trading_signals` | Generated BUY/SELL/HOLD signals |
| `order_executions` | Executed/logged orders |

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## Viewing Results

### Dashboard
Start the server and visit http://127.0.0.1:8000/dashboard to see:
- **Signal Engine Executions** — All BUY/SELL/HOLD signals with strength, event type, impact, and confidence
- **News Feed** — Ingested articles with sources and tickers
- **Ticker States** — Current state of each tracked company

### API
- `GET /executions` — All order execution records
- `GET /signals` — All trading signals
- `GET /api/dashboard-data` — Full dashboard data as JSON

### Database
Query the SQLite database directly:
```bash
sqlite3 data/trading_bot.db "SELECT ticker, signal, strength, impact_score, confidence FROM trading_signals ORDER BY created_at DESC LIMIT 10;"
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## License

This project is intended for educational and research purposes. Use at your own risk.

---

## Acknowledgments

- [Zerodha Kite Connect](https://kite.trade/) for the trading API
- [Google Gemini AI](https://ai.google.dev/) for sentiment analysis
- [GNews](https://gnews.io/) for news data
- [FAISS](https://github.com/facebookresearch/faiss) for vector similarity search