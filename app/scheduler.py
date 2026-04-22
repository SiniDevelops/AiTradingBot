"""
Background scheduler for the trading bot.

Two loops run concurrently:
1. NEWS LOOP (every 5 min): GNews -> Gemini -> Signal -> Execute
2. MARKET LOOP (every 1 min): Refresh prices -> Re-evaluate signals
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Optional

from app import db
from app.gnews_fetcher import GNewsFetcher
from app.llm_analyzer import get_llm_provider
from app.signal_engine import get_signal_engine
from app.zerodha_executor import get_zerodha_executor
from app.ingest import ingest_and_dedupe, update_news_tickers
from app.ticker_linker import link_tickers
from app.rag import get_vector_store
from app.state_manager import StateManager
from app.market_data import fetch_market_context
from app.utils import extract_sentences


# Intervals (seconds)
NEWS_INTERVAL = int(os.getenv("NEWS_INTERVAL_SECONDS", "300"))  # 5 min
MARKET_INTERVAL = int(os.getenv("MARKET_INTERVAL_SECONDS", "60"))  # 1 min

# Track which tickers we're actively monitoring
_active_tickers: set = set()
# Store the latest analysis for each ticker (for re-evaluation)
_latest_analyses: dict = {}


def _log(tag: str, msg: str):
    """Print a timestamped log message."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{tag}] {msg}")


async def news_loop():
    """
    Fetch news, analyze with Gemini, generate signals, execute.
    Runs every NEWS_INTERVAL seconds.
    """
    _log("SCHEDULER", f"News loop started (every {NEWS_INTERVAL}s)")

    # Small initial delay to let the server start
    await asyncio.sleep(5)

    while True:
        try:
            _log("NEWS", "--- Starting news fetch cycle ---")

            # Initialize fetcher
            try:
                fetcher = GNewsFetcher()
            except ValueError as e:
                _log("NEWS", f"GNews not configured: {e}")
                await asyncio.sleep(NEWS_INTERVAL)
                continue

            # Fetch news
            news_requests = fetcher.fetch_and_convert(max_per_query=2)

            if not news_requests:
                _log("NEWS", "No articles found")
                await asyncio.sleep(NEWS_INTERVAL)
                continue

            _log("NEWS", f"Got {len(news_requests)} articles")

            llm_provider = get_llm_provider()
            signal_engine = get_signal_engine()
            executor = get_zerodha_executor()

            articles_processed = 0
            signals_generated = {"BUY": 0, "SELL": 0, "HOLD": 0}

            for news_req in news_requests[:10]:  # Cap at 10 per cycle
                # Ingest
                is_new, news_id, _ = ingest_and_dedupe(news_req)
                if not is_new:
                    continue

                # Link tickers
                tickers = link_tickers(news_req.content, news_req.title)
                update_news_tickers(news_id, tickers)

                if not tickers:
                    continue

                articles_processed += 1
                _log("NEWS", f"Processing: {news_req.title[:60]}... -> {', '.join(tickers)}")

                # Add to active tickers
                _active_tickers.update(tickers)

                # Analyze each ticker
                vector_store = get_vector_store()
                summary = extract_sentences(news_req.content, max_sentences=2)

                for ticker in tickers:
                    vector_store.add_chunk(
                        ticker=ticker, layer="profile",
                        source_id=news_id, snippet=summary,
                        timestamp=news_req.published_at,
                    )

                for ticker in tickers:
                    # Ensure profile exists
                    if not db.get_profile(ticker):
                        db.insert_or_update_profile(ticker, f"Default profile for {ticker}.")

                    # Retrieve context
                    query = f"{news_req.title} {ticker}"
                    retrieved_chunks = vector_store.retrieve_for_ticker(ticker, query, top_k=6)

                    # LLM Analysis
                    article_excerpt = extract_sentences(news_req.content, max_sentences=3)
                    analysis = llm_provider.analyze(
                        ticker=ticker,
                        article_excerpt=article_excerpt,
                        title=news_req.title,
                        retrieved_context=retrieved_chunks,
                    )

                    # Store latest analysis for market loop re-evaluation
                    _latest_analyses[ticker] = {
                        "analysis": analysis,
                        "news_id": news_id,
                        "timestamp": datetime.now(),
                    }

                    # State management
                    StateManager.process_analysis(
                        analysis=analysis, ticker=ticker,
                        source_id=news_id, published_at=news_req.published_at,
                    )
                    StateManager.commit_state_snapshot(ticker)

                    vector_store.add_chunk(
                        ticker=ticker, layer="state",
                        source_id=news_id, snippet=analysis.summary,
                        timestamp=news_req.published_at,
                    )

                    # Audit
                    chunks_json = json.dumps([
                        {"layer": c.layer, "source_id": c.source_id, "snippet": c.snippet}
                        for c in retrieved_chunks
                    ])
                    audit_id = db.insert_analysis_run(
                        news_id=news_id,
                        tickers_json=json.dumps([ticker]),
                        retrieved_chunks_json=chunks_json,
                        llm_output_json=analysis.model_dump_json(),
                    )

                    # Fetch market data + generate signal
                    market_ctx = fetch_market_context(ticker)
                    signal_result = signal_engine.generate_signal(
                        analysis=analysis,
                        news_id=news_id,
                        audit_id=audit_id,
                        market_context=market_ctx,
                    )

                    # Persist signal
                    signal_id = db.insert_signal(
                        ticker=signal_result.ticker,
                        signal=signal_result.signal.value,
                        strength=signal_result.strength,
                        impact_score=signal_result.impact_score,
                        confidence=signal_result.confidence,
                        event_type=signal_result.event_type,
                        reasons_json=json.dumps(signal_result.reasons),
                        news_impact_summary=signal_result.news_impact_summary,
                        news_id=signal_result.news_id,
                        audit_id=signal_result.audit_id,
                    )

                    sig = signal_result.signal.value
                    signals_generated[sig] = signals_generated.get(sig, 0) + 1
                    _log("NEWS", f"  {ticker}: {sig} (strength={signal_result.strength:.2f})")

                    # Execute
                    exec_result = executor.execute_signal(signal_result)
                    db.insert_order_execution(
                        signal_id=signal_id,
                        ticker=exec_result["ticker"],
                        order_type=exec_result["action_taken"],
                        quantity=exec_result["quantity"],
                        order_id=exec_result.get("order_id"),
                        status=exec_result["status"],
                        message=exec_result["message"],
                        trading_mode=executor.trading_mode,
                    )

            _log("NEWS", f"Cycle complete: {articles_processed} articles, "
                 f"BUY={signals_generated['BUY']} SELL={signals_generated['SELL']} "
                 f"HOLD={signals_generated['HOLD']}")

        except Exception as e:
            _log("NEWS", f"Error in news loop: {e}")

        _log("NEWS", f"Next cycle in {NEWS_INTERVAL}s")
        await asyncio.sleep(NEWS_INTERVAL)


async def market_loop():
    """
    Re-fetch market data and re-evaluate signals for active tickers.
    Runs every MARKET_INTERVAL seconds.

    This catches situations where:
    - RSI just crossed below 30 (oversold) -> might flip HOLD to BUY
    - Price dropped sharply -> existing positive analysis becomes stronger
    - SMA crossover happened -> trend change affects signal
    """
    _log("SCHEDULER", f"Market loop started (every {MARKET_INTERVAL}s)")

    # Wait for the news loop to populate some tickers first
    await asyncio.sleep(30)

    while True:
        try:
            if not _active_tickers:
                await asyncio.sleep(MARKET_INTERVAL)
                continue

            tickers_to_check = list(_active_tickers)
            _log("MARKET", f"Refreshing {len(tickers_to_check)} tickers: "
                 f"{', '.join(tickers_to_check[:5])}{'...' if len(tickers_to_check) > 5 else ''}")

            signal_engine = get_signal_engine()
            executor = get_zerodha_executor()

            for ticker in tickers_to_check:
                # Get latest analysis for this ticker
                latest = _latest_analyses.get(ticker)
                if not latest:
                    continue

                # Skip if the analysis is more than 30 min old
                age_minutes = (datetime.now() - latest["timestamp"]).total_seconds() / 60
                if age_minutes > 30:
                    continue

                analysis = latest["analysis"]
                news_id = latest["news_id"]

                # Fetch fresh market data
                market_ctx = fetch_market_context(ticker)
                if not market_ctx.data_available:
                    continue

                # Re-generate signal with fresh market data
                signal_result = signal_engine.generate_signal(
                    analysis=analysis,
                    news_id=news_id,
                    market_context=market_ctx,
                )

                # Only act on BUY/SELL signals (not HOLD)
                if signal_result.signal.value in ("BUY", "SELL"):
                    _log("MARKET", f"  [!] {ticker}: {signal_result.signal.value} "
                         f"(strength={signal_result.strength:.2f}, "
                         f"price=Rs.{market_ctx.current_price:.2f}, "
                         f"RSI={market_ctx.rsi_14:.0f})")

                    # Persist the re-evaluated signal
                    signal_id = db.insert_signal(
                        ticker=signal_result.ticker,
                        signal=signal_result.signal.value,
                        strength=signal_result.strength,
                        impact_score=signal_result.impact_score,
                        confidence=signal_result.confidence,
                        event_type=signal_result.event_type,
                        reasons_json=json.dumps(signal_result.reasons),
                        news_impact_summary=signal_result.news_impact_summary + " [MARKET RE-EVAL]",
                        news_id=signal_result.news_id,
                        audit_id=signal_result.audit_id,
                    )

                    # Execute
                    exec_result = executor.execute_signal(signal_result)
                    db.insert_order_execution(
                        signal_id=signal_id,
                        ticker=exec_result["ticker"],
                        order_type=exec_result["action_taken"],
                        quantity=exec_result["quantity"],
                        order_id=exec_result.get("order_id"),
                        status=exec_result["status"],
                        message=exec_result["message"],
                        trading_mode=executor.trading_mode,
                    )
                else:
                    _log("MARKET", f"  {ticker}: HOLD "
                         f"(price=Rs.{market_ctx.current_price:.2f}, "
                         f"RSI={market_ctx.rsi_14:.0f}, SMA={market_ctx.sma_signal})")

        except Exception as e:
            _log("MARKET", f"Error in market loop: {e}")

        await asyncio.sleep(MARKET_INTERVAL)


async def start_scheduler():
    """Start both loops as background tasks."""
    _log("SCHEDULER", "=" * 50)
    _log("SCHEDULER", "  AUTOMATED SCHEDULER STARTING")
    _log("SCHEDULER", f"  News fetch: every {NEWS_INTERVAL // 60} min")
    _log("SCHEDULER", f"  Market check: every {MARKET_INTERVAL}s")
    _log("SCHEDULER", f"  Trading mode: {os.getenv('TRADING_MODE', 'paper')}")
    _log("SCHEDULER", "=" * 50)

    # Run both loops concurrently
    await asyncio.gather(
        news_loop(),
        market_loop(),
    )
