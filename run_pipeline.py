"""
Standalone end-to-end pipeline script.
Runs the full flow: GNews → Gemini → Signal → Zerodha

Usage:
    .\\venv\\Scripts\\python run_pipeline.py
    .\\venv\\Scripts\\python run_pipeline.py --query "Reliance Industries"
    .\\venv\\Scripts\\python run_pipeline.py --max-articles 5
"""
import os
import sys
import json
import argparse
from datetime import datetime

# Load .env before any app imports
from dotenv import load_dotenv
load_dotenv()

from app import db
from app.gnews_fetcher import GNewsFetcher
from app.llm_analyzer import get_llm_provider
from app.signal_engine import get_signal_engine
from app.zerodha_executor import ZerodhaExecutor
from app.ingest import ingest_and_dedupe, update_news_tickers
from app.ticker_linker import link_tickers
from app.rag import get_vector_store
from app.state_manager import StateManager
from app.utils import extract_sentences
from app.models import SignalResult, SignalType
from app.market_data import fetch_market_context


def print_banner():
    """Print a banner for the pipeline run."""
    print("=" * 70)
    print("  AI TRADING BOT - End-to-End Pipeline")
    print("  GNews -> Gemini -> Signal Engine -> Zerodha")
    print("=" * 70)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Trading Mode: {os.getenv('TRADING_MODE', 'paper')}")
    print("=" * 70)
    print()


def run_pipeline(
    queries=None,
    max_articles=5,
):
    """Run the full pipeline once."""

    print_banner()

    # ==== Step 0: Initialize ====
    print("[INIT] Initializing database...")
    db.init_db()

    print("[INIT] Initializing LLM provider...")
    llm_provider = get_llm_provider()
    provider_name = type(llm_provider).__name__
    print(f"[INIT] LLM Provider: {provider_name}")

    print("[INIT] Initializing signal engine...")
    signal_engine = get_signal_engine()

    print("[INIT] Initializing Zerodha executor...")
    executor = ZerodhaExecutor()
    executor.authenticate()
    print(f"[INIT] Zerodha authenticated: {executor.authenticated}")
    print(f"[INIT] Trading mode: {executor.trading_mode}")
    print()

    # ==== Step 1: Fetch News from GNews ====
    print("=" * 70)
    print("  STEP 1: Fetching News from GNews API")
    print("=" * 70)

    try:
        fetcher = GNewsFetcher()
    except ValueError as e:
        print(f"[ERROR] GNews not configured: {e}")
        return

    news_requests = fetcher.fetch_and_convert(
        queries=queries,
        max_per_query=max(1, max_articles // 3),
    )

    if not news_requests:
        print("[ERROR] No news articles returned from GNews. Exiting.")
        return

    print(f"\n[OK] Got {len(news_requests)} articles from GNews")
    for i, req in enumerate(news_requests[:max_articles], 1):
        print(f"  {i}. [{req.source}] {req.title[:80]}...")
    print()

    # ==== Step 2-5: Process each article ====
    print("=" * 70)
    print("  STEP 2-5: Ingest -> Analyze -> Signal -> Execute")
    print("=" * 70)

    total_signals = {"BUY": 0, "SELL": 0, "HOLD": 0}
    total_executions = []
    processed = 0

    for i, news_req in enumerate(news_requests[:max_articles], 1):
        print(f"\n{'---' * 20}")
        print(f"  Article {i}/{min(len(news_requests), max_articles)}")
        print(f"  Title: {news_req.title[:70]}...")
        print(f"  Source: {news_req.source}")
        print(f"{'---' * 20}")

        # Step 2: Ingest
        is_new, news_id, _ = ingest_and_dedupe(news_req)

        if not is_new:
            print(f"  [SKIP] Duplicate article, already ingested")
            continue

        # Link tickers
        tickers = link_tickers(news_req.content, news_req.title)
        update_news_tickers(news_id, tickers)

        if not tickers:
            print(f"  [SKIP] No recognizable tickers found in article")
            continue

        print(f"  [OK] Ingested as {news_id}")
        print(f"  [OK] Tickers found: {', '.join(tickers)}")

        # Fetch live market data for all tickers
        print(f"  [Market] Fetching live prices...")
        market_data = {}
        for t in tickers:
            market_data[t] = fetch_market_context(t)

        # Step 3: Analyze with Gemini
        vector_store = get_vector_store()

        # Add article to vector store
        summary = extract_sentences(news_req.content, max_sentences=2)
        for ticker in tickers:
            vector_store.add_chunk(
                ticker=ticker,
                layer="profile",
                source_id=news_id,
                snippet=summary,
                timestamp=news_req.published_at,
            )

        for ticker in tickers:
            print(f"\n  Analyzing {ticker}...")

            # Ensure profile exists
            profile = db.get_profile(ticker)
            if not profile:
                db.insert_or_update_profile(
                    ticker, f"Default profile for {ticker}."
                )

            # Retrieve context
            query = f"{news_req.title} {ticker} {extract_sentences(news_req.content, 2)}"
            retrieved_chunks = vector_store.retrieve_for_ticker(
                ticker, query, top_k=6
            )

            # LLM Analysis
            article_excerpt = extract_sentences(news_req.content, max_sentences=3)
            analysis = llm_provider.analyze(
                ticker=ticker,
                article_excerpt=article_excerpt,
                title=news_req.title,
                retrieved_context=retrieved_chunks,
            )

            print(f"  [Gemini] Event: {analysis.event_type}, "
                  f"Impact: {analysis.impact_score:+.2f}, "
                  f"Confidence: {analysis.confidence:.0%}")
            print(f"  [Gemini] Summary: {analysis.summary[:100]}")

            # State management
            published_at = news_req.published_at
            success, message = StateManager.process_analysis(
                analysis=analysis,
                ticker=ticker,
                source_id=news_id,
                published_at=published_at,
            )
            StateManager.commit_state_snapshot(ticker)

            # Add to vector store
            vector_store.add_chunk(
                ticker=ticker,
                layer="state",
                source_id=news_id,
                snippet=analysis.summary,
                timestamp=published_at,
            )

            # Audit record
            retrieved_chunks_json = json.dumps([
                {"layer": c.layer, "source_id": c.source_id, "snippet": c.snippet}
                for c in retrieved_chunks
            ])
            audit_id = db.insert_analysis_run(
                news_id=news_id,
                tickers_json=json.dumps([ticker]),
                retrieved_chunks_json=retrieved_chunks_json,
                llm_output_json=analysis.model_dump_json(),
            )

            # Step 4: Generate signal (with market data)
            mkt_ctx = market_data.get(ticker)
            signal_result = signal_engine.generate_signal(
                analysis=analysis,
                news_id=news_id,
                audit_id=audit_id,
                market_context=mkt_ctx,
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

            signal_emoji = {"BUY": "[BUY]", "SELL": "[SELL]", "HOLD": "[HOLD]"}
            sig_val = signal_result.signal.value
            print(f"  {signal_emoji.get(sig_val, '?')} Signal: {sig_val} "
                  f"(strength={signal_result.strength:.2f})")
            total_signals[sig_val] = total_signals.get(sig_val, 0) + 1

            # Step 5: Execute via Zerodha
            exec_result = executor.execute_signal(signal_result)
            total_executions.append(exec_result)

            # Persist execution
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

            print(f"  [Exec] Status: {exec_result['status']} - {exec_result['message'][:80]}")

        processed += 1

    # ==== Summary ====
    print()
    print("=" * 70)
    print("  PIPELINE COMPLETE - SUMMARY")
    print("=" * 70)
    print(f"  Articles processed: {processed}")
    print(f"  Signals generated:")
    print(f"    [+] BUY:  {total_signals.get('BUY', 0)}")
    print(f"    [-] SELL: {total_signals.get('SELL', 0)}")
    print(f"    [=] HOLD: {total_signals.get('HOLD', 0)}")
    print(f"  Orders executed/logged: {len(total_executions)}")
    print(f"  Trading mode: {executor.trading_mode}")
    print(f"  Zerodha authenticated: {executor.authenticated}")
    print(f"  LLM provider: {provider_name}")
    print("=" * 70)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Run the AI Trading Bot pipeline: GNews → Gemini → Zerodha"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        nargs="+",
        help="Search queries for GNews (e.g., 'Reliance Industries' 'TCS')",
    )
    parser.add_argument(
        "--max-articles", "-m",
        type=int,
        default=5,
        help="Maximum number of articles to process (default: 5)",
    )

    args = parser.parse_args()
    run_pipeline(
        queries=args.query,
        max_articles=args.max_articles,
    )


if __name__ == "__main__":
    main()
