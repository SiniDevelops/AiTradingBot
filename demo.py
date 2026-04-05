"""
Demo script: Run the complete pipeline with sample data.
No server required - direct function calls.
"""
import json
from datetime import datetime
import sys
import os

# Ensure app module is importable
sys.path.insert(0, os.path.dirname(__file__))

from app import db
from app.models import NewsIngestRequest
from app.ingest import ingest_and_dedupe, update_news_tickers
from app.ticker_linker import link_tickers
from app.rag import get_vector_store
from app.llm_analyzer import get_llm_provider
from app.state_manager import StateManager
from data.sample_data import SAMPLE_NEWS, EXPECTED_ANALYSES


def print_section(title):
    """Pretty print a section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)


def print_check(msg):
    """Print check mark with message."""
    print(f"[OK] {msg}")


def print_info(msg):
    """Print info message."""
    print(f"[*] {msg}")


def print_error(msg):
    """Print error message."""
    print(f"[!] {msg}")


def demo_pipeline():
    """Run complete pipeline with sample data."""
    
    print_section("INITIALIZING DATABASE")
    db.init_db()
    print_check("Database initialized")
    
    # Create profiles
    db.insert_or_update_profile("AAPL", "Apple Inc. - Technology company, leader in consumer electronics")
    db.insert_or_update_profile("GOOGL", "Alphabet/Google - Search, advertising, and cloud services")
    db.insert_or_update_profile("MSFT", "Microsoft - Software, cloud computing, and enterprise services")
    print_check("Ticker profiles created")
    
    print_section("PROCESSING SAMPLE NEWS ARTICLES")
    
    vector_store = get_vector_store()
    llm_provider = get_llm_provider()
    
    results = []
    
    for i, news_data in enumerate(SAMPLE_NEWS, 1):
        print(f"\n[Article {i}/{len(SAMPLE_NEWS)}] {news_data['title']}")
        print("-" * 80)
        
        # Step 1: Ingest
        news_request = NewsIngestRequest(**news_data)
        is_new, news_id, _ = ingest_and_dedupe(news_request)
        
        if not is_new:
            print(f"  [WARNING] DUPLICATE: Article already exists, skipping")
            continue
        
        print(f"  [OK] Ingested: news_id={news_id}")
        
        # Step 2: Extract tickers
        tickers = link_tickers(news_data['content'], news_data['title'])
        update_news_tickers(news_id, tickers)
        print(f"  [OK] Extracted tickers: {tickers}")
        
        # Step 3: Add to vector store (profile layer)
        for ticker in tickers:
            vector_store.add_chunk(
                ticker=ticker,
                layer="profile",
                source_id=news_id,
                snippet=news_data['title'][:100],
                timestamp=datetime.fromisoformat(news_data['published_at'])
            )
        print(f"  [OK] Added to vector store")
        
        # Step 4: Process each ticker
        for ticker in tickers:
            print(f"\n  Processing ticker: {ticker}")
            
            # Retrieve context
            query = f"{news_data['title']} {ticker}"
            retrieved = vector_store.retrieve_for_ticker(ticker, query, top_k=3)
            print(f"    - Retrieved {len(retrieved)} context chunks")
            
            # LLM Analysis
            analysis = llm_provider.analyze(
                ticker=ticker,
                article_excerpt=news_data['content'][:300],
                title=news_data['title'],
                retrieved_context=retrieved
            )
            
            print(f"    - Event type: {analysis.event_type}")
            print(f"    - Impact score: {analysis.impact_score:.2f}")
            print(f"    - Severity: {analysis.severity}")
            print(f"    - Confidence: {analysis.confidence:.2f}")
            print(f"    - Summary: {analysis.summary[:60]}...")
            
            # State update (Option B)
            published_at = datetime.fromisoformat(news_data['published_at'])
            success, msg = StateManager.process_analysis(
                analysis=analysis,
                ticker=ticker,
                source_id=news_id,
                published_at=published_at
            )
            
            if success:
                print(f"    - State updated: {msg}")
            else:
                print(f"    - State update skipped: {msg}")
            
            # Rebuild and commit state
            state = StateManager.commit_state_snapshot(ticker)
            print(f"    - State snapshot saved")
            
            # Add to vector store (state layer)
            vector_store.add_chunk(
                ticker=ticker,
                layer="state",
                source_id=news_id,
                snippet=analysis.summary,
                timestamp=published_at
            )
            
            # Store audit record
            audit_id = db.insert_analysis_run(
                news_id=news_id,
                tickers_json=json.dumps([ticker]),
                retrieved_chunks_json=json.dumps([
                    {"layer": c.layer, "source_id": c.source_id, "snippet": c.snippet}
                    for c in retrieved
                ]),
                llm_output_json=analysis.model_dump_json()
            )
            
            print(f"    - Audit record ID: {audit_id}")
            
            results.append({
                "ticker": ticker,
                "analysis": analysis.model_dump(),
                "audit_id": audit_id
            })
    
    print_section("PIPELINE COMPLETED")
    print(f"\nProcessed {len(results)} ticker-analyses")
    
    # Display results
    print_section("ANALYSIS RESULTS SUMMARY")
    
    for result in results:
        ticker = result["ticker"]
        analysis = result["analysis"]
        
        print(f"\n{ticker}:")
        print(f"  Event Type      : {analysis['event_type']}")
        print(f"  Impact Score    : {analysis['impact_score']:+.2f}")
        print(f"  Severity        : {analysis['severity'].upper()}")
        print(f"  Confidence      : {analysis['confidence']:.0%}")
        print(f"  Horizon         : {analysis['horizon']}")
        print(f"  Summary         : {analysis['summary']}")
    
    # Display current states
    print_section("CURRENT TICKER STATES")
    
    unique_tickers = set(r["ticker"] for r in results)
    for ticker in sorted(unique_tickers):
        state = StateManager.get_current_state(ticker)
        
        if state:
            print(f"\n{ticker} - {state.last_updated.isoformat()}")
            print(f"  Open Events: {len(state.open_events)}")
            for event in state.open_events:
                print(f"    - [{event.severity.upper()}] {event.event_type}: {event.summary[:60]}")
            print(f"  Recent Catalysts: {len(state.recent_catalysts)}")
            print(f"  Key Risks: {len(state.key_risks)}")
            for risk in state.key_risks[:3]:
                print(f"    - {risk[:60]}")
    
    # Display events history
    print_section("EVENT HISTORY")
    
    for ticker in sorted(unique_tickers):
        events = db.get_state_events_by_ticker(ticker)
        
        if events:
            print(f"\n{ticker}: {len(events)} total event(s)")
            for event in events[:5]:  # Show first 5
                status = "[CLOSED]" if event["status"] == "closed" else "[OPEN]  "
                print(f"  {status} | {event['event_type']:15} | {event['summary'][:50]}")
    
    # Display audit records
    print_section("AUDIT TRAIL SAMPLE")
    
    for result in results[:2]:  # Show first 2 audits
        audit_id = result["audit_id"]
        audit = db.get_analysis_run(audit_id)
        
        if audit:
            print(f"\nAudit ID {audit_id}:")
            print(f"  News ID: {audit['news_id']}")
            print(f"  Tickers: {json.loads(audit['tickers_json'])}")
            llm_output = json.loads(audit['llm_output_json'])
            print(f"  LLM Output Event Type: {llm_output['event_type']}")
            print(f"  Impact Score: {llm_output['impact_score']:.2f}")
    
    print_section("DEMO COMPLETE")
    print("\nNext steps:")
    print("  1. Start API: .\\venv\\Scripts\\uvicorn app.main:app --host 127.0.0.1 --port 8000")
    print("  2. Docs: http://127.0.0.1:8000/docs")
    print("  3. Query state: curl http://127.0.0.1:8000/state/AAPL")
    print("  4. Run tests: .\\venv\\Scripts\\pytest tests/ -v")
    

if __name__ == "__main__":
    demo_pipeline()
