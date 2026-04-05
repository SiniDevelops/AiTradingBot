"""
FastAPI main application for Company State RAG trading bot.
Implements endpoints for news ingestion, analysis, state querying,
signal generation, and dashboard.
"""
import json
import os
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn

from app import db
from app.models import (
    NewsIngestRequest,
    IngestResponse,
    AnalyzeResponse,
    StateResponse,
    LLMImpactAnalysis
)
from app.ingest import ingest_and_dedupe, update_news_tickers
from app.ticker_linker import link_tickers
from app.rag import get_vector_store
from app.llm_analyzer import get_llm_provider, create_analysis_prompt
from app.state_manager import StateManager
from app.signal_engine import get_signal_engine
from app.utils import extract_sentences

# Initialize FastAPI app
app = FastAPI(
    title="Company State RAG Trading Bot",
    description="News-driven trading bot with RAG and conflict resolution",
    version="0.2.0"
)


# ============ Lifecycle Events ============
@app.on_event("startup")
async def startup_event():
    """Initialize database and vector store on startup."""
    db.init_db()
    print("Database initialized")


# ============ Health Check ============
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ============ News Ingestion Endpoint ============
@app.post("/ingest_news", response_model=IngestResponse)
async def ingest_news(request: NewsIngestRequest):
    """
    Ingest and deduplicate news article.
    
    Steps:
    1. Clean text
    2. Check for duplicates via hash
    3. Extract tickers using alias dictionary
    4. Persist raw + clean records
    5. Add profile chunks to vector store
    """
    try:
        # Step 1-2: Ingest and dedupe
        is_new, news_id, _ = ingest_and_dedupe(request)
        
        if not is_new:
            return IngestResponse(
                news_id=news_id,
                tickers=[],
                status="duplicate"
            )
        
        # Step 3: Link tickers
        tickers = link_tickers(request.content, request.title)
        
        # Update news with extracted tickers
        update_news_tickers(news_id, tickers)
        
        # Step 5: Add article summary to vector store as profile layer
        vector_store = get_vector_store()
        summary = extract_sentences(request.content, max_sentences=2)
        for ticker in tickers:
            vector_store.add_chunk(
                ticker=ticker,
                layer="profile",
                source_id=news_id,
                snippet=summary,
                timestamp=request.published_at
            )
        
        return IngestResponse(
            news_id=news_id,
            tickers=tickers,
            status="ingested"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Analysis Endpoint ============
@app.post("/analyze_news/{news_id}", response_model=List[AnalyzeResponse])
async def analyze_news(news_id: str):
    """
    Analyze ingested news article for each ticker.
    
    Steps:
    1. Load cleaned article and tickers
    2. For each ticker:
       a. Retrieve context (profile + state + events)
       b. Call LLM analyzer
       c. Process analysis (Option B state merge)
       d. Commit state snapshot
       e. Store audit record
       f. Generate trading signal
    """
    try:
        # Load news
        news_raw = db.get_news_raw(news_id)
        news_clean = db.get_news_clean(news_id)
        
        if not news_raw or not news_clean:
            raise HTTPException(status_code=404, detail="News not found")
        
        # Parse tickers
        tickers = json.loads(news_clean["tickers_json"])
        
        if not tickers:
            raise HTTPException(status_code=400, detail="No tickers found in article")
        
        results = []
        signal_engine = get_signal_engine()
        
        # Process each ticker
        for ticker in tickers:
            # Ensure profile exists (create if not)
            profile = db.get_profile(ticker)
            if not profile:
                default_profile = f"Default profile for {ticker}. Add specific info later."
                db.insert_or_update_profile(ticker, default_profile)
            
            # Step 2a: Retrieve context
            vector_store = get_vector_store()
            query = f"{news_raw['title']} {ticker} {extract_sentences(news_raw['content'], 2)}"
            retrieved_chunks = vector_store.retrieve_for_ticker(ticker, query, top_k=6)
            
            # Step 2b: LLM Analysis
            llm_provider = get_llm_provider()
            article_excerpt = extract_sentences(news_raw["content"], max_sentences=3)
            
            analysis = llm_provider.analyze(
                ticker=ticker,
                article_excerpt=article_excerpt,
                title=news_raw["title"],
                retrieved_context=retrieved_chunks
            )
            
            # Step 2c: Process with state manager (Option B)
            published_at = datetime.fromisoformat(news_raw["published_at"]) if isinstance(news_raw["published_at"], str) else news_raw["published_at"]
            success, message = StateManager.process_analysis(
                analysis=analysis,
                ticker=ticker,
                source_id=news_id,
                published_at=published_at
            )
            
            if not success:
                print(f"State update failed for {ticker}: {message}")
            
            # Step 2d: Commit state snapshot
            state = StateManager.commit_state_snapshot(ticker)
            
            # Add analysis summary to vector store as state layer
            vector_store.add_chunk(
                ticker=ticker,
                layer="state",
                source_id=news_id,
                snippet=analysis.summary,
                timestamp=published_at
            )
            
            # Step 2e: Store audit record
            retrieved_chunks_json = json.dumps([
                {
                    "layer": c.layer,
                    "source_id": c.source_id,
                    "snippet": c.snippet
                }
                for c in retrieved_chunks
            ])
            
            audit_id = db.insert_analysis_run(
                news_id=news_id,
                tickers_json=json.dumps([ticker]),
                retrieved_chunks_json=retrieved_chunks_json,
                llm_output_json=analysis.model_dump_json()
            )
            
            # Step 2f: Generate trading signal
            signal_result = signal_engine.generate_signal(
                analysis=analysis,
                news_id=news_id,
                audit_id=audit_id,
            )
            
            # Persist signal to database
            db.insert_signal(
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
            
            print(f"Signal: {signal_result.signal.value} {signal_result.ticker} "
                  f"(strength={signal_result.strength:.2f})")
            
            results.append(AnalyzeResponse(
                news_id=news_id,
                ticker=ticker,
                analysis=analysis,
                audit_id=audit_id
            ))
        
        return results
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ State Query Endpoint ============
@app.get("/state/{ticker}", response_model=StateResponse)
async def get_state(ticker: str):
    """
    Retrieve current state snapshot for a ticker.
    
    Returns:
    - Open events
    - Recent catalysts
    - Key risks
    - Last updated timestamp
    """
    try:
        state = StateManager.get_current_state(ticker)
        
        if not state:
            raise HTTPException(status_code=404, detail=f"No state found for {ticker}")
        
        return StateResponse(ticker=ticker, state=state)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Events History Endpoint ============
@app.get("/events/{ticker}")
async def get_events(ticker: str, status: Optional[str] = None):
    """
    Retrieve event history for a ticker.
    
    Query params:
    - status: filter by 'open' or 'closed'
    """
    try:
        events = db.get_state_events_by_ticker(ticker, status=status)
        
        # Convert datetime objects to ISO strings
        for event in events:
            if isinstance(event.get("start_ts"), str):
                event["start_ts"] = event["start_ts"]
            else:
                event["start_ts"] = event["start_ts"].isoformat()
            
            if event.get("end_ts"):
                if isinstance(event["end_ts"], str):
                    event["end_ts"] = event["end_ts"]
                else:
                    event["end_ts"] = event["end_ts"].isoformat()
        
        return {"ticker": ticker, "events": events, "count": len(events)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Audit Log Endpoint ============
@app.get("/audit/{audit_id}")
async def get_audit(audit_id: int):
    """
    Retrieve audit record of an analysis run.
    """
    try:
        audit = db.get_analysis_run(audit_id)
        
        if not audit:
            raise HTTPException(status_code=404, detail="Audit record not found")
        
        # Parse JSON fields
        audit["tickers"] = json.loads(audit["tickers_json"])
        audit["retrieved_chunks"] = json.loads(audit["retrieved_chunks_json"])
        audit["llm_output"] = json.loads(audit["llm_output_json"])
        
        return audit
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Batch Analysis Endpoint ============
@app.post("/batch_analyze")
async def batch_analyze(news_list: List[NewsIngestRequest]):
    """
    Ingest and analyze multiple news articles in batch.
    """
    try:
        results = []
        
        for news in news_list:
            # Ingest
            ingest_response = await ingest_news(news)
            
            # If new, analyze
            if ingest_response.status == "ingested":
                analyses = await analyze_news(ingest_response.news_id)
                results.append({
                    "news_id": ingest_response.news_id,
                    "ingest": ingest_response.model_dump(),
                    "analyses": [a.model_dump() for a in analyses]
                })
            else:
                results.append({
                    "news_id": ingest_response.news_id,
                    "status": "duplicate"
                })
        
        return {"results": results}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Signal Endpoints ============
@app.get("/signals/{ticker}")
async def get_signals_for_ticker(ticker: str, limit: int = 20):
    """Get recent trading signals for a ticker."""
    signals = db.get_signals_by_ticker(ticker, limit)
    for s in signals:
        s["reasons"] = json.loads(s["reasons_json"])
        del s["reasons_json"]
    return {"ticker": ticker, "signals": signals, "count": len(signals)}


@app.get("/signals")
async def get_all_signals(limit: int = 50):
    """Get all recent trading signals."""
    signals = db.get_recent_signals(limit)
    for s in signals:
        s["reasons"] = json.loads(s["reasons_json"])
        del s["reasons_json"]
    return {"signals": signals, "count": len(signals)}


# ============ Dashboard Endpoints ============
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML page."""
    template_path = os.path.join(
        os.path.dirname(__file__), "templates", "dashboard.html"
    )
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@app.get("/api/dashboard-data")
async def dashboard_data():
    """JSON data endpoint for the dashboard (polled every 10s)."""
    # Get recent signals
    signals = db.get_recent_signals(50)
    for s in signals:
        s["reasons"] = json.loads(s["reasons_json"])
        del s["reasons_json"]

    # Get recent news
    with db.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT nr.id, nr.source, nr.published_at, nr.title,
                   nc.tickers_json
            FROM news_raw nr
            LEFT JOIN news_clean nc ON nr.id = nc.id
            ORDER BY nr.created_at DESC
            LIMIT 30
        """)
        news_items = []
        for row in cursor.fetchall():
            item = dict(row)
            if item.get("tickers_json"):
                item["tickers"] = json.loads(item["tickers_json"])
            else:
                item["tickers"] = []
            if "tickers_json" in item:
                del item["tickers_json"]
            news_items.append(item)

    # Get analysis runs with LLM output
    with db.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, news_id, tickers_json, llm_output_json, created_at
            FROM analysis_runs
            ORDER BY created_at DESC
            LIMIT 30
        """)
        analyses = []
        for row in cursor.fetchall():
            item = dict(row)
            item["tickers"] = json.loads(item["tickers_json"])
            item["llm_output"] = json.loads(item["llm_output_json"])
            del item["tickers_json"]
            del item["llm_output_json"]
            analyses.append(item)

    # Get ticker states
    with db.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ticker, state_json, updated_at FROM state_snapshot")
        states = {}
        for row in cursor.fetchall():
            item = dict(row)
            states[item["ticker"]] = json.loads(item["state_json"])

    return {
        "signals": signals,
        "news": news_items,
        "analyses": analyses,
        "states": states,
        "timestamp": datetime.now().isoformat(),
    }


# ============ Main Entry Point ============
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )
