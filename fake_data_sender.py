"""
Fake Data Sender — Sequential test data for the Trading Bot.

Sends 15 timed news articles to the API covering progressive storylines
across multiple tickers, then displays the resulting signals.

Usage:
    .\\venv\\Scripts\\python fake_data_sender.py --delay 5
    .\\venv\\Scripts\\python fake_data_sender.py --delay 3 --base-url http://127.0.0.1:8000
"""
import argparse
import sys
import time
import json
from datetime import datetime, timedelta

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Install with: pip install httpx")
    sys.exit(1)

# ═══════════════ Configuration ═══════════════
BASE_URL = "http://127.0.0.1:8000"

# ANSI color codes for console output
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    GRAY = "\033[90m"

# ═══════════════ Fake News Data ═══════════════
# Progressive storylines across 5 tickers
# Each article builds on previous ones to test state management

BASE_TIME = datetime.utcnow()

FAKE_NEWS = [
    # ── AAPL Arc: Earnings beat → Guidance raise → Lawsuit → Lawsuit dismissed ──
    {
        "id": "fake_001",
        "source": "Bloomberg",
        "published_at": (BASE_TIME - timedelta(hours=14)).isoformat() + "Z",
        "title": "Apple Reports Record Q1 Revenue, Beats Analyst Estimates",
        "content": (
            "Apple Inc. (AAPL) reported quarterly revenue of $94.8 billion for Q1 2025, "
            "surpassing Wall Street estimates of $92.1 billion. The company's earnings per share "
            "came in at $2.45, beating consensus of $2.28. CEO Tim Cook highlighted strong demand "
            "for Apple Vision Pro and services revenue growing 18% year-over-year. iPhone sales "
            "remained robust despite broader smartphone market weakness. Ticker: $AAPL. "
            "The results mark Apple's strongest quarter since 2022."
        ),
    },
    {
        "id": "fake_002",
        "source": "Reuters",
        "published_at": (BASE_TIME - timedelta(hours=13)).isoformat() + "Z",
        "title": "Apple Raises Full-Year Revenue Guidance to $420 Billion",
        "content": (
            "Following its strong Q1 earnings beat, Apple Inc. ($AAPL) has raised its full-year "
            "revenue guidance to $415-420 billion, up from the prior range of $400-410 billion. "
            "CFO Luca Maestri cited accelerating services growth and better-than-expected iPhone 16 "
            "demand in China. Analysts view the guidance raise as a strong bullish signal. "
            "Morgan Stanley raised its price target on AAPL to $240 from $215."
        ),
    },
    {
        "id": "fake_003",
        "source": "WSJ",
        "published_at": (BASE_TIME - timedelta(hours=12)).isoformat() + "Z",
        "title": "Apple Sued by DOJ Over App Store Monopoly Practices",
        "content": (
            "The U.S. Department of Justice filed a landmark antitrust lawsuit against Apple Inc. "
            "(AAPL), alleging the company maintains an illegal monopoly over the smartphone market "
            "through its App Store policies. The lawsuit seeks to force Apple to allow third-party "
            "app stores and sideloading on iPhones. Apple shares fell 3.2% on the news. "
            "Legal analysts estimate the case could take 2-3 years to resolve. $AAPL."
        ),
    },
    {
        "id": "fake_004",
        "source": "Bloomberg",
        "published_at": (BASE_TIME - timedelta(hours=5)).isoformat() + "Z",
        "title": "DOJ Drops Apple Antitrust Case After Settlement Agreement",
        "content": (
            "The Department of Justice has dismissed its antitrust lawsuit against Apple Inc. "
            "(AAPL) after reaching a settlement agreement. Apple agreed to reduce App Store "
            "commission rates to 15% for small developers and allow limited third-party payment "
            "processing. The resolved settlement removes a major legal overhang from the stock. "
            "AAPL shares rallied 4.1% on the announcement. Analysts called the settlement "
            "favorable for Apple."
        ),
    },

    # ── GOOGL Arc: AI concerns → Product launch → Regulatory probe resolved ──
    {
        "id": "fake_005",
        "source": "TechCrunch",
        "published_at": (BASE_TIME - timedelta(hours=11)).isoformat() + "Z",
        "title": "Google AI Search Faces Accuracy Concerns, Stock Dips",
        "content": (
            "Alphabet Inc. (GOOGL) shares declined 2.8% after reports surfaced that Google's "
            "AI-powered search results have been generating inaccurate summaries in medical and "
            "financial queries. The SEC announced it would investigate whether these AI features "
            "could constitute misleading information to consumers. Google stated it is working on "
            "improving accuracy and cooperating with regulators. Ticker: GOOGL."
        ),
    },
    {
        "id": "fake_006",
        "source": "The Verge",
        "published_at": (BASE_TIME - timedelta(hours=8)).isoformat() + "Z",
        "title": "Google Launches Gemini Ultra 2.0, Most Advanced AI Model Yet",
        "content": (
            "Alphabet (GOOGL) unveiled Gemini Ultra 2.0, its most capable AI model to date, "
            "outperforming GPT-5 on 28 of 32 industry benchmarks. The launch includes enterprise "
            "APIs integrated with Google Cloud, positioned to capture growing enterprise AI spending. "
            "Early partner feedback has been overwhelmingly positive. GOOGL shares rose 3.5% in "
            "after-hours trading. Analysts estimate Gemini could add $15B in annual cloud revenue."
        ),
    },
    {
        "id": "fake_007",
        "source": "Reuters",
        "published_at": (BASE_TIME - timedelta(hours=3)).isoformat() + "Z",
        "title": "SEC Clears Google of AI Search Misconduct Allegations",
        "content": (
            "The Securities and Exchange Commission has concluded its investigation into Google's "
            "AI search features, finding no evidence of intentional consumer deception. The resolved "
            "inquiry removes a significant regulatory cloud from Alphabet (GOOGL). The company's "
            "compliance improvements were noted positively. GOOGL shares gained 1.8% on the news."
        ),
    },

    # ── MSFT Arc: AI partnership → Cloud earnings beat → Guidance upgrade ──
    {
        "id": "fake_008",
        "source": "CNBC",
        "published_at": (BASE_TIME - timedelta(hours=10)).isoformat() + "Z",
        "title": "Microsoft Expands OpenAI Partnership with $15B Additional Investment",
        "content": (
            "Microsoft Corporation (MSFT) announced a $15 billion expansion of its partnership "
            "with OpenAI, bringing total investment to $28 billion. The deal includes exclusive "
            "enterprise licensing for GPT-5 and integration across Microsoft 365, Azure, and "
            "Dynamics products. CEO Satya Nadella called it 'the most important strategic move "
            "in Microsoft's history.' MSFT shares surged 4.2% on the announcement."
        ),
    },
    {
        "id": "fake_009",
        "source": "Bloomberg",
        "published_at": (BASE_TIME - timedelta(hours=7)).isoformat() + "Z",
        "title": "Microsoft Azure Revenue Grows 42%, Crushing Expectations",
        "content": (
            "Microsoft (MSFT) reported Azure cloud revenue growth of 42% year-over-year, well "
            "above the 35% consensus estimate. AI workloads drove a significant portion of the "
            "acceleration, with enterprise AI consumption on Azure tripling. Total quarterly "
            "revenue reached $68.5 billion. EPS beat expectations by $0.12. MSFT stock hit "
            "all-time highs in after-hours trading."
        ),
    },

    # ── TSLA Arc: Production miss → Price cuts → Recovery ──
    {
        "id": "fake_010",
        "source": "Reuters",
        "published_at": (BASE_TIME - timedelta(hours=9)).isoformat() + "Z",
        "title": "Tesla Misses Q1 Production Targets by 15%, Shares Tumble",
        "content": (
            "Tesla Inc. (TSLA) reported Q1 2025 production of 410,000 vehicles, missing its "
            "target of 480,000 by 15%. The shortfall was attributed to supply chain disruptions "
            "at the Berlin Gigafactory and slower-than-expected Cybertruck ramp. TSLA shares "
            "fell 8.5% in pre-market trading. Analysts at Goldman Sachs downgraded the stock "
            "to Neutral, citing margin pressure. $TSLA."
        ),
    },
    {
        "id": "fake_011",
        "source": "WSJ",
        "published_at": (BASE_TIME - timedelta(hours=6)).isoformat() + "Z",
        "title": "Tesla Slashes Model 3 and Model Y Prices by 10% Globally",
        "content": (
            "Tesla (TSLA) announced a 10% price reduction across Model 3 and Model Y lineups "
            "in all markets, its deepest global cut yet. The aggressive pricing strategy signals "
            "potential demand weakness and margin deterioration. Gross automotive margins are "
            "expected to fall below 15% for the first time. Competitor BYD praised the move as "
            "validation of its own pricing strategy. $TSLA declined 3.1% following the announcement."
        ),
    },
    {
        "id": "fake_012",
        "source": "Bloomberg",
        "published_at": (BASE_TIME - timedelta(hours=2)).isoformat() + "Z",
        "title": "Tesla Reports Surging Orders After Price Cuts, Backlog Grows 40%",
        "content": (
            "Tesla Inc. ($TSLA) reported that global orders surged 40% in the two weeks following "
            "its price cuts, with the Model Y becoming the best-selling vehicle in Europe and China. "
            "CEO Elon Musk stated on X that 'volume growth is back' and hinted at restored guidance. "
            "While margin concerns remain, analysts noted that higher volume could offset per-unit "
            "profitability decline. TSLA shares rose 5.7% on the positive order data."
        ),
    },

    # ── NVDA Arc: AI chip demand → Supply warning → New chip launch ──
    {
        "id": "fake_013",
        "source": "Bloomberg",
        "published_at": (BASE_TIME - timedelta(hours=8)).isoformat() + "Z",
        "title": "NVIDIA Reports AI Chip Demand Outstripping Supply by 3x",
        "content": (
            "NVIDIA Corporation (NVDA) CEO Jensen Huang revealed that demand for the company's "
            "H200 and B100 AI accelerators is exceeding supply by a factor of three. Data center "
            "revenue is expected to grow 200% year-over-year. Major cloud providers including "
            "Microsoft, Google, and Amazon have placed multi-billion dollar orders. NVDA shares "
            "surged 6.3% to new all-time highs. $NVDA."
        ),
    },
    {
        "id": "fake_014",
        "source": "Reuters",
        "published_at": (BASE_TIME - timedelta(hours=4)).isoformat() + "Z",
        "title": "NVIDIA Warns of Potential Supply Constraints Through 2025",
        "content": (
            "NVIDIA ($NVDA) cautioned investors that supply constraints for its AI GPU products "
            "could persist through the end of 2025 due to TSMC capacity limitations. While demand "
            "remains strong, the company may not be able to fully capitalize on the AI boom in the "
            "near term. Some analysts flagged this as an ambiguous signal — supply constraints "
            "confirm strong demand but limit near-term revenue upside. NVDA slipped 1.5%."
        ),
    },
    {
        "id": "fake_015",
        "source": "TechCrunch",
        "published_at": (BASE_TIME - timedelta(hours=1)).isoformat() + "Z",
        "title": "NVIDIA Unveils Blackwell B200 GPU with 2x Performance Gains",
        "content": (
            "NVIDIA (NVDA) launched its next-generation Blackwell B200 GPU at GTC 2025, "
            "demonstrating a 2x performance improvement over the H100 at the same power envelope. "
            "The B200 introduces new FP4 precision support optimized for inference workloads. "
            "Cloud partners are expected to begin deployments in Q3 2025. NVDA shares jumped "
            "7.2% on the announcement. Jensen Huang called it 'the engine of the AI industrial "
            "revolution.' $NVDA."
        ),
    },
]


# ═══════════════ Sending Logic ═══════════════

def print_header():
    """Print startup header."""
    print(f"\n{C.BOLD}{C.MAGENTA}{'='*70}{C.RESET}")
    print(f"{C.BOLD}{C.MAGENTA}  FAKE DATA SENDER — Trading Bot Test Harness{C.RESET}")
    print(f"{C.MAGENTA}{'='*70}{C.RESET}")
    print(f"{C.DIM}  Sending {len(FAKE_NEWS)} articles sequentially to the API{C.RESET}")
    print(f"{C.DIM}  Dashboard: http://127.0.0.1:8000/dashboard{C.RESET}")
    print(f"{C.MAGENTA}{'='*70}{C.RESET}\n")


def send_article(client: httpx.Client, article: dict, index: int, total: int, base_url: str):
    """Send a single article: ingest → analyze → print results."""

    print(f"{C.BOLD}{C.CYAN}[{index}/{total}]{C.RESET} {C.BOLD}{article['title'][:65]}{C.RESET}")
    print(f"  {C.DIM}Source: {article['source']} | ID: {article['id']}{C.RESET}")

    # Step 1: Ingest
    try:
        resp = client.post(f"{base_url}/ingest_news", json=article, timeout=30)
        if resp.status_code != 200:
            print(f"  {C.RED}INGEST FAILED: HTTP {resp.status_code} — {resp.text[:100]}{C.RESET}")
            return None
        ingest_data = resp.json()
        status = ingest_data.get("status", "?")
        tickers = ingest_data.get("tickers", [])

        if status == "duplicate":
            print(f"  {C.YELLOW}DUPLICATE — already ingested, skipping{C.RESET}")
            return None

        print(f"  {C.GREEN}Ingested{C.RESET} | Tickers: {C.BOLD}{', '.join(tickers)}{C.RESET}")

    except Exception as e:
        print(f"  {C.RED}INGEST ERROR: {e}{C.RESET}")
        return None

    # Step 2: Analyze
    news_id = ingest_data.get("news_id", article["id"])
    try:
        resp = client.post(f"{base_url}/analyze_news/{news_id}", timeout=30)
        if resp.status_code != 200:
            print(f"  {C.RED}ANALYZE FAILED: HTTP {resp.status_code} — {resp.text[:100]}{C.RESET}")
            return None
        analyses = resp.json()

        for a in analyses:
            analysis = a.get("analysis", {})
            ticker = a.get("ticker", "?")
            event_type = analysis.get("event_type", "?")
            impact = analysis.get("impact_score", 0)
            severity = analysis.get("severity", "?")
            confidence = analysis.get("confidence", 0)

            impact_color = C.GREEN if impact > 0.1 else C.RED if impact < -0.1 else C.GRAY
            print(f"  {C.BLUE}Analysis:{C.RESET} {C.BOLD}{ticker}{C.RESET} | "
                  f"type={event_type} | "
                  f"impact={impact_color}{impact:+.2f}{C.RESET} | "
                  f"severity={severity} | "
                  f"confidence={confidence:.0%}")

    except Exception as e:
        print(f"  {C.RED}ANALYZE ERROR: {e}{C.RESET}")
        return None

    # Step 3: Check signals
    try:
        resp = client.get(f"{base_url}/signals", timeout=10)
        if resp.status_code == 200:
            sig_data = resp.json()
            recent = sig_data.get("signals", [])
            # Find signals from this news_id
            new_signals = [s for s in recent if s.get("news_id") == news_id]
            for s in new_signals:
                sig_type = s.get("signal", "?")
                sig_color = C.GREEN if sig_type == "BUY" else C.RED if sig_type == "SELL" else C.GRAY
                strength = s.get("strength", 0)
                print(f"  {C.BOLD}{sig_color}>>> SIGNAL: {sig_type}{C.RESET} "
                      f"{C.BOLD}{s.get('ticker', '?')}{C.RESET} "
                      f"(strength={strength:.2f})")
    except Exception:
        pass  # Non-critical

    return analyses


def countdown(seconds: int):
    """Show countdown timer."""
    for remaining in range(seconds, 0, -1):
        sys.stdout.write(f"\r  {C.DIM}Next article in {remaining}s...{C.RESET}  ")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\r" + " " * 40 + "\r")
    sys.stdout.flush()


def print_summary(base_url: str, client: httpx.Client):
    """Print final summary of all signals."""
    print(f"\n{C.BOLD}{C.MAGENTA}{'='*70}{C.RESET}")
    print(f"{C.BOLD}{C.MAGENTA}  SUMMARY{C.RESET}")
    print(f"{C.MAGENTA}{'='*70}{C.RESET}")

    try:
        resp = client.get(f"{base_url}/signals?limit=100", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            signals = data.get("signals", [])

            buy_count = sum(1 for s in signals if s["signal"] == "BUY")
            sell_count = sum(1 for s in signals if s["signal"] == "SELL")
            hold_count = sum(1 for s in signals if s["signal"] == "HOLD")

            print(f"\n  Total Signals: {C.BOLD}{len(signals)}{C.RESET}")
            print(f"  {C.GREEN}BUY:  {buy_count}{C.RESET}")
            print(f"  {C.RED}SELL: {sell_count}{C.RESET}")
            print(f"  {C.GRAY}HOLD: {hold_count}{C.RESET}")

            # Per-ticker breakdown
            tickers = {}
            for s in signals:
                t = s["ticker"]
                if t not in tickers:
                    tickers[t] = {"BUY": 0, "SELL": 0, "HOLD": 0}
                tickers[t][s["signal"]] += 1

            if tickers:
                print(f"\n  {'Ticker':<8} {'BUY':>5} {'SELL':>5} {'HOLD':>5}")
                print(f"  {'─'*28}")
                for ticker in sorted(tickers.keys()):
                    counts = tickers[ticker]
                    print(f"  {C.BOLD}{ticker:<8}{C.RESET} "
                          f"{C.GREEN}{counts['BUY']:>5}{C.RESET} "
                          f"{C.RED}{counts['SELL']:>5}{C.RESET} "
                          f"{C.GRAY}{counts['HOLD']:>5}{C.RESET}")

    except Exception as e:
        print(f"  {C.RED}Could not fetch summary: {e}{C.RESET}")

    print(f"\n{C.MAGENTA}{'='*70}{C.RESET}")
    print(f"  {C.DIM}Dashboard: {base_url}/dashboard{C.RESET}")
    print(f"{C.MAGENTA}{'='*70}{C.RESET}\n")


def main(args):
    """Main entry point."""
    base_url = args.base_url.rstrip("/")
    delay = args.delay

    print_header()

    # Verify server is running
    client = httpx.Client()
    try:
        resp = client.get(f"{base_url}/health", timeout=5)
        if resp.status_code != 200:
            print(f"{C.RED}Server health check failed! Is the server running?{C.RESET}")
            print(f"{C.DIM}Start with: .\\venv\\Scripts\\uvicorn app.main:app --host 127.0.0.1 --port 8000{C.RESET}")
            sys.exit(1)
        print(f"{C.GREEN}Server is healthy{C.RESET} ({base_url})\n")
    except Exception:
        print(f"{C.RED}Cannot connect to server at {base_url}{C.RESET}")
        print(f"{C.DIM}Start with: .\\venv\\Scripts\\uvicorn app.main:app --host 127.0.0.1 --port 8000{C.RESET}")
        sys.exit(1)

    # Send articles
    total = len(FAKE_NEWS)
    for i, article in enumerate(FAKE_NEWS, 1):
        send_article(client, article, i, total, base_url)

        if i < total:
            print()
            countdown(delay)

    # Print summary
    print_summary(base_url, client)
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Send fake news data to the Trading Bot API for testing"
    )
    parser.add_argument(
        "--delay", type=int, default=5,
        help="Seconds between each article (default: 5)"
    )
    parser.add_argument(
        "--base-url", type=str, default=BASE_URL,
        help=f"API base URL (default: {BASE_URL})"
    )
    args = parser.parse_args()
    main(args)
