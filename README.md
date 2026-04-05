# AiTradingBot

An AI-powered automated trading system for the Indian stock market (NSE) using Zerodha's Kite Connect API. Combines technical analysis strategies with machine learning and sentiment analysis to execute trades with built-in risk management.

> **Disclaimer:** This project is for **educational purposes only**. Real trading involves significant financial risk. Always test thoroughly with paper trading before considering live deployment. Ensure compliance with SEBI regulations and Zerodha's terms of service.

---

## Features

- **Multiple Trading Strategies** — Moving Average Crossover, RSI, and Random Forest ML model working together via a consensus mechanism
- **News Sentiment Analysis** — Uses Google Gemini AI and VADER for real-time market sentiment scoring
- **Risk Management** — Position sizing, daily loss limits, stop-loss/take-profit, trade cooldowns, and max concurrent position controls
- **Paper & Live Trading** — Full simulation mode for testing before going live
- **Backtesting Engine** — Validate strategies against historical data with performance metrics (win rate, Sharpe ratio, drawdown)
- **Web Dashboard** — FastAPI-based monitoring interface
- **Telegram Alerts** — Real-time trade notifications
- **Docker Support** — One-command deployment with Docker Compose

---

## Tech Stack

| Category | Technologies |
|---|---|
| **Core** | Python 3.11+, FastAPI, Uvicorn |
| **Market Data** | Zerodha Kite Connect API |
| **ML/AI** | scikit-learn (Random Forest), TensorFlow, Google Generative AI, VADER Sentiment |
| **Database** | MongoDB, Motor (async), PyMongo |
| **Visualization** | Matplotlib, Seaborn, Plotly |
| **DevOps** | Docker, Docker Compose |
| **Testing** | pytest, pytest-asyncio |
| **Code Quality** | Ruff, Black |

---

## Project Structure

```
AiTradingBot/
├── main.py                  # Entry point
├── app.py                   # FastAPI application
├── strategy_engine.py       # Core strategy orchestration
├── kite_auth.py             # Zerodha authentication
├── market_data.py           # Real-time data handling
├── order_manager.py         # Trade execution
├── risk_manager.py          # Risk controls
├── backtester.py            # Backtesting engine
├── monitor.py               # Health monitoring
├── config.py                # Configuration loader
├── settings.yaml            # Trading parameters
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── src/
│   ├── api/                 # REST API endpoints
│   ├── auth/                # Authentication logic
│   ├── strategy/            # Strategy modules
│   │   ├── sentiment_analyzer.py
│   │   └── strategy_engine.py
│   ├── data/                # Data handling
│   │   ├── market_data.py
│   │   └── news_fetcher.py
│   ├── backtest/            # Backtesting modules
│   ├── execution/           # Trade execution logic
│   ├── risk/                # Risk management
│   ├── monitoring/          # Monitoring & logging
│   ├── dashboard/           # Web dashboard
│   └── utils/               # Utility functions
├── tests/
│   └── test_sentiment.py
└── logs/                    # Runtime logs
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- A [Zerodha Kite Connect](https://kite.trade/) subscription (₹2,000/month)
- MongoDB (local or cloud instance)
- *(Optional)* Docker & Docker Compose

### Installation

```bash
git clone https://github.com/SiniDevelops/AiTradingBot.git
cd AiTradingBot
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

1. Copy the environment template and fill in your credentials:

```bash
cp .env.example .env
```

2. Set the required environment variables in `.env`:

| Variable | Description |
|---|---|
| `KITE_API_KEY` | Zerodha API key |
| `KITE_API_SECRET` | Zerodha API secret |
| `KITE_REQUEST_TOKEN` | OAuth request token |
| `TRADING_MODE` | `paper` or `live` |

Optional variables:

| Variable | Description |
|---|---|
| `MONGODB_URI` | MongoDB connection string |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for alerts |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for alerts |
| `GNEWS_API_KEY` | GNews API key for news fetching |
| `GEMINI_API_KEY` | Google Gemini API key for sentiment analysis |
| `MAX_CAPITAL_PER_TRADE` | Max capital per trade (default: ₹10,000) |
| `DAILY_LOSS_LIMIT` | Daily loss limit (default: ₹3,000) |

3. Review and adjust trading parameters in `settings.yaml` as needed.

---

## Usage

### Server & Dashboard

To run the web dashboard, signal engine, and API:

```bash
.\venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Then navigate to: `http://127.0.0.1:8000/dashboard`


### Fake Data Testing 

To test the news ingestion, impact analysis, and signal engine using the built-in test harness, wait for the server to spin up and then run: 

```bash
.\venv\Scripts\python fake_data_sender.py --delay 3
```

This acts as a simulator, sending 15 progressive news articles sequentially and displaying the generated trading signals dynamically.

### Paper Trading (Recommended First Step)

```bash
python main.py --mode paper
```

### Live Trading

```bash
python main.py --mode live
```

### Backtesting

```bash
python main.py --mode backtest
```

### Docker Deployment

```bash
docker-compose up -d
```

This starts four services:

| Service | Description | Port |
|---|---|---|
| Trading Bot | Main bot process | — |
| API | FastAPI dashboard | `8000` |
| MongoDB | Data persistence | `27017` |
| Mongo Express | Database UI | `8081` |

---

## Trading Strategies

### 1. Moving Average Crossover
Uses EMA(9) and EMA(21) crossover signals for trend-following entries and exits.

### 2. RSI (Relative Strength Index)
Trades on oversold/overbought conditions (period: 14) with trend filtering to avoid counter-trend trades.

### 3. Machine Learning — Random Forest
Trained on 200 days of historical data using technical indicators as features. Disabled by default — enable in `settings.yaml`.

### 4. Consensus Mechanism
Requires **≥2 strategies to agree** before executing a trade, reducing false signals.

### 5. News Sentiment Analysis
Fetches and analyzes market news every 5 minutes using Gemini AI and VADER scoring to filter trades by sentiment.

---

## Risk Management

| Parameter | Default |
|---|---|
| Total Capital | ₹100,000 |
| Max Per Trade | ₹10,000 (10%) |
| Daily Loss Limit | ₹3,000 |
| Stop Loss | 2% per position |
| Take Profit | 4% per position |
| Max Concurrent Positions | 5 |
| Trade Cooldown | 300 seconds per symbol |
| Confidence Threshold | 60% |

---

## Default Watchlist

The bot monitors these NSE stocks by default (configurable in `settings.yaml`):

RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, BHARTIARTL, ITC

---

## Running Tests

```bash
pytest tests/ -v
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
- [Google Generative AI](https://ai.google.dev/) for sentiment analysis
- [VADER Sentiment](https://github.com/cjhutto/vaderSentiment) for sentiment scoring