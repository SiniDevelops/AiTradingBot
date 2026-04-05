"""
News ingestion and deduplication module.
"""
import json
from datetime import datetime
from typing import List, Tuple
from app.db import insert_news_raw, insert_news_clean, check_news_hash_exists
from app.utils import hash_text, clean_text, extract_sentences
from app.models import NewsIngestRequest


def ingest_and_dedupe(news_request: NewsIngestRequest) -> Tuple[bool, str, List[str]]:
    """
    Ingest news, check for duplicates, and return tickers.
    
    Returns:
        (is_new: bool, news_id: str, tickers: List[str])
    """
    # Clean the content
    content = news_request.content
    cleaned_text = clean_text(content)
    
    # Extract key sentences for context
    summary = extract_sentences(content, max_sentences=3)
    
    # Create hash for deduplication
    combined_text = f"{news_request.title}:{cleaned_text}"
    hash_val = hash_text(combined_text)
    
    # Check if duplicate
    if check_news_hash_exists(hash_val):
        return False, news_request.id, []
    
    # Insert raw news
    success_raw = insert_news_raw(
        news_id=news_request.id,
        source=news_request.source,
        published_at=news_request.published_at,
        title=news_request.title,
        content=news_request.content
    )
    
    if not success_raw:
        return False, news_request.id, []
    
    # Placeholder: ticker extraction happens separately (in ticker_linker)
    # For now, return empty list; ticker_linker will extract these
    tickers = []
    
    # Insert cleaned news (tickers will be added after linking)
    tickers_json = json.dumps(tickers)
    success_clean = insert_news_clean(
        news_id=news_request.id,
        cleaned_text=cleaned_text,
        hash_val=hash_val,
        tickers_json=tickers_json
    )
    
    if not success_clean:
        return False, news_request.id, []
    
    return True, news_request.id, tickers


def update_news_tickers(news_id: str, tickers: List[str]):
    """Update tickers for a news item after linking."""
    import sqlite3
    from app.db import get_db
    
    tickers_json = json.dumps(tickers)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE news_clean SET tickers_json = ? WHERE id = ?
        """, (tickers_json, news_id))
        conn.commit()
