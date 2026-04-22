"""
SQLite database setup and query functions.
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "trading_bot.db")


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize database schema."""
    with get_db() as conn:
        cursor = conn.cursor()

        # ========== News Tables ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_raw (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                published_at DATETIME NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_clean (
                id TEXT PRIMARY KEY,
                cleaned_text TEXT NOT NULL,
                hash TEXT UNIQUE NOT NULL,
                tickers_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id) REFERENCES news_raw(id)
            )
        """)

        # ========== Ticker Profile Tables ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticker_profile (
                ticker TEXT PRIMARY KEY,
                profile_text TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ========== State Event Tables ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                severity TEXT NOT NULL,
                impact_score REAL NOT NULL,
                horizon TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_id TEXT NOT NULL,
                start_ts DATETIME NOT NULL,
                end_ts DATETIME,
                confidence REAL NOT NULL,
                evidence TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticker) REFERENCES ticker_profile(ticker)
            )
        """)

        # Index for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_state_events_ticker_status
            ON state_events(ticker, status)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_snapshot (
                ticker TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticker) REFERENCES ticker_profile(ticker)
            )
        """)

        # ========== Vector Store Metadata Table ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vector_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                layer TEXT NOT NULL,
                source_id TEXT NOT NULL,
                snippet TEXT NOT NULL,
                embedding_vector BLOB,
                timestamp DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticker) REFERENCES ticker_profile(ticker)
            )
        """)

        # ========== Audit Table ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                news_id TEXT NOT NULL,
                tickers_json TEXT NOT NULL,
                retrieved_chunks_json TEXT NOT NULL,
                llm_output_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (news_id) REFERENCES news_raw(id)
            )
        """)

        # ========== Trading Signals Table ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trading_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                signal TEXT NOT NULL,
                strength REAL NOT NULL,
                impact_score REAL NOT NULL,
                confidence REAL NOT NULL,
                event_type TEXT NOT NULL,
                reasons_json TEXT NOT NULL,
                news_impact_summary TEXT NOT NULL,
                news_id TEXT NOT NULL,
                audit_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (news_id) REFERENCES news_raw(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trading_signals_ticker
            ON trading_signals(ticker, created_at DESC)
        """)

        # ========== Order Executions Table ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                ticker TEXT NOT NULL,
                order_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                order_id TEXT,
                status TEXT NOT NULL,
                message TEXT,
                trading_mode TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_id) REFERENCES trading_signals(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_order_executions_ticker
            ON order_executions(ticker, created_at DESC)
        """)

        conn.commit()
        print(f"Database initialized at {DB_PATH}")


# ========== News Operations ==========
def insert_news_raw(news_id: str, source: str, published_at: datetime, title: str, content: str):
    """Insert raw news record."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO news_raw (id, source, published_at, title, content)
                VALUES (?, ?, ?, ?, ?)
            """, (news_id, source, published_at, title, content))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def insert_news_clean(news_id: str, cleaned_text: str, hash_val: str, tickers_json: str):
    """Insert cleaned news record."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO news_clean (id, cleaned_text, hash, tickers_json)
                VALUES (?, ?, ?, ?)
            """, (news_id, cleaned_text, hash_val, tickers_json))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def get_news_raw(news_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve raw news by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM news_raw WHERE id = ?", (news_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_news_clean(news_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve cleaned news by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM news_clean WHERE id = ?", (news_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def check_news_hash_exists(hash_val: str) -> bool:
    """Check if news with given hash already exists."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM news_clean WHERE hash = ?", (hash_val,))
        return cursor.fetchone() is not None


# ========== Ticker Profile Operations ==========
def insert_or_update_profile(ticker: str, profile_text: str):
    """Insert or update ticker profile."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ticker_profile (ticker, profile_text, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ticker) DO UPDATE SET
                profile_text = ?,
                updated_at = CURRENT_TIMESTAMP
        """, (ticker, profile_text, profile_text))
        conn.commit()


def get_profile(ticker: str) -> Optional[Dict[str, Any]]:
    """Retrieve ticker profile."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ticker_profile WHERE ticker = ?", (ticker,))
        row = cursor.fetchone()
        return dict(row) if row else None


# ========== State Event Operations ==========
def insert_state_event(
    ticker: str,
    event_type: str,
    status: str,
    severity: str,
    impact_score: float,
    horizon: str,
    summary: str,
    source_id: str,
    start_ts: datetime,
    end_ts: Optional[datetime],
    confidence: float,
    evidence: str
) -> int:
    """Insert a state event. Returns the event ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO state_events
            (ticker, event_type, status, severity, impact_score, horizon, summary,
             source_id, start_ts, end_ts, confidence, evidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, event_type, status, severity, impact_score, horizon, summary,
              source_id, start_ts, end_ts, confidence, evidence))
        conn.commit()
        return cursor.lastrowid


def get_state_events_by_ticker(ticker: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get state events for a ticker, optionally filtered by status."""
    with get_db() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("""
                SELECT * FROM state_events
                WHERE ticker = ? AND status = ?
                ORDER BY start_ts DESC
            """, (ticker, status))
        else:
            cursor.execute("""
                SELECT * FROM state_events
                WHERE ticker = ?
                ORDER BY start_ts DESC
            """, (ticker,))
        return [dict(row) for row in cursor.fetchall()]


def update_state_event(event_id: int, **kwargs):
    """Update state event fields."""
    with get_db() as conn:
        cursor = conn.cursor()
        # Build dynamic UPDATE query
        allowed_fields = {"status", "severity", "impact_score", "horizon", "summary", "confidence", "evidence", "end_ts"}
        fields_to_update = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not fields_to_update:
            return
        
        set_clause = ", ".join([f"{k} = ?" for k in fields_to_update.keys()])
        values = list(fields_to_update.values()) + [event_id]
        
        cursor.execute(f"UPDATE state_events SET {set_clause} WHERE id = ?", values)
        conn.commit()


def find_similar_open_events(ticker: str, event_type: str, summary: str) -> List[Dict[str, Any]]:
    """Find open events of same type for a ticker."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM state_events
            WHERE ticker = ? AND event_type = ? AND status = 'open'
            ORDER BY start_ts DESC
        """, (ticker, event_type))
        return [dict(row) for row in cursor.fetchall()]


# ========== State Snapshot Operations ==========
def insert_or_update_snapshot(ticker: str, state_json: str):
    """Insert or update state snapshot."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO state_snapshot (ticker, state_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ticker) DO UPDATE SET
                state_json = ?,
                updated_at = CURRENT_TIMESTAMP
        """, (ticker, state_json, state_json))
        conn.commit()


def get_snapshot(ticker: str) -> Optional[Dict[str, Any]]:
    """Retrieve state snapshot."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM state_snapshot WHERE ticker = ?", (ticker,))
        row = cursor.fetchone()
        return dict(row) if row else None


# ========== Vector Store Operations ==========
def insert_vector_chunk(ticker: str, layer: str, source_id: str, snippet: str, timestamp: Optional[datetime] = None):
    """Insert vector chunk with metadata."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vector_chunks (ticker, layer, source_id, snippet, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (ticker, layer, source_id, snippet, timestamp))
        conn.commit()


def get_vector_chunks_by_ticker(ticker: str) -> List[Dict[str, Any]]:
    """Get all vector chunks for a ticker."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM vector_chunks
            WHERE ticker = ?
            ORDER BY created_at DESC
        """, (ticker,))
        return [dict(row) for row in cursor.fetchall()]


# ========== Audit Operations ==========
def insert_analysis_run(news_id: str, tickers_json: str, retrieved_chunks_json: str, llm_output_json: str) -> int:
    """Insert audit record. Returns the audit ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO analysis_runs (news_id, tickers_json, retrieved_chunks_json, llm_output_json)
            VALUES (?, ?, ?, ?)
        """, (news_id, tickers_json, retrieved_chunks_json, llm_output_json))
        conn.commit()
        return cursor.lastrowid


def get_analysis_run(audit_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve audit record."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM analysis_runs WHERE id = ?", (audit_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# ========== Trading Signal Operations ==========
def insert_signal(ticker: str, signal: str, strength: float, impact_score: float,
                  confidence: float, event_type: str, reasons_json: str,
                  news_impact_summary: str, news_id: str,
                  audit_id: Optional[int] = None) -> int:
    """Insert a trading signal. Returns the signal ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO trading_signals
            (ticker, signal, strength, impact_score, confidence, event_type,
             reasons_json, news_impact_summary, news_id, audit_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, signal, strength, impact_score, confidence, event_type,
              reasons_json, news_impact_summary, news_id, audit_id))
        conn.commit()
        return cursor.lastrowid


def get_recent_signals(limit: int = 50) -> List[Dict[str, Any]]:
    """Get most recent trading signals across all tickers."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM trading_signals
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_signals_by_ticker(ticker: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent signals for a specific ticker."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM trading_signals
            WHERE ticker = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (ticker, limit))
        return [dict(row) for row in cursor.fetchall()]


# ========== Order Execution Operations ==========
def insert_order_execution(
    signal_id: Optional[int],
    ticker: str,
    order_type: str,
    quantity: int,
    order_id: Optional[str],
    status: str,
    message: str,
    trading_mode: str,
) -> int:
    """Insert an order execution record. Returns the execution ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO order_executions
            (signal_id, ticker, order_type, quantity, order_id, status, message, trading_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (signal_id, ticker, order_type, quantity, order_id, status, message, trading_mode))
        conn.commit()
        return cursor.lastrowid


def get_recent_executions(limit: int = 50) -> List[Dict[str, Any]]:
    """Get most recent order executions."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM order_executions
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
