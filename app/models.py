"""
Pydantic models for Company State RAG system.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


# ============ News Models ============
class NewsIngestRequest(BaseModel):
    """Input schema for news ingestion."""
    id: str
    source: str
    published_at: datetime
    title: str
    content: str


class NewsRaw(BaseModel):
    """Raw news record."""
    id: str
    source: str
    published_at: datetime
    title: str
    content: str


class NewsClean(BaseModel):
    """Cleaned news record."""
    id: str
    cleaned_text: str
    hash: str
    tickers_json: str  # JSON list of ticker strings


# ============ Ticker Profile Models ============
class TickerProfile(BaseModel):
    """Long-term ticker profile."""
    ticker: str
    profile_text: str
    updated_at: datetime


# ============ State Event Models ============
class StateEvent(BaseModel):
    """A single state event record."""
    id: Optional[int] = None
    ticker: str
    event_type: Literal["lawsuit", "earnings", "guidance", "product_launch", "regulatory", "macro", "other"]
    status: Literal["open", "closed"]
    severity: Literal["low", "med", "high"]
    impact_score: float = Field(..., ge=-1.0, le=1.0)
    horizon: Literal["intraday", "swing", "long"]
    summary: str
    source_id: str
    start_ts: datetime
    end_ts: Optional[datetime] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: str
    created_at: Optional[datetime] = None


class StateSnapshot(BaseModel):
    """Current state snapshot for a ticker."""
    ticker: str
    state_json: str  # Serialized structured state object
    updated_at: datetime


# ============ Analysis/Impact Models ============
class LLMImpactAnalysis(BaseModel):
    """Structured impact analysis output from LLM."""
    ticker: str
    event_type: Literal["lawsuit", "earnings", "guidance", "product_launch", "regulatory", "macro", "other"]
    is_new_information: bool
    impact_score: float = Field(..., ge=-1.0, le=1.0)
    horizon: Literal["intraday", "swing", "long"]
    severity: Literal["low", "med", "high"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_flags: List[Literal["rumor", "low_quality_source", "ambiguous", "already_priced_in"]]
    contradiction_flags: List[Literal["conflicts_with_guidance", "conflicts_with_state", "none"]]
    summary: str
    evidence: str
    citations: List[dict] = Field(default_factory=list)


class RetrievedChunk(BaseModel):
    """A chunk retrieved from vector store."""
    layer: Literal["profile", "state", "event"]
    source_id: str
    snippet: str
    timestamp: Optional[datetime] = None
    metadata: Optional[dict] = None


# ============ Audit Models ============
class AnalysisRun(BaseModel):
    """Audit log of an analysis run."""
    id: Optional[int] = None
    news_id: str
    tickers_json: str
    retrieved_chunks_json: str
    llm_output_json: str
    created_at: Optional[datetime] = None


# ============ Structured State Models ============
class OpenEvent(BaseModel):
    """Open event summary in state snapshot."""
    event_type: str
    summary: str
    start_ts: datetime
    severity: str
    impact_score: float
    horizon: str
    confidence: float
    source_id: str


class RecentCatalyst(BaseModel):
    """Recent catalyst in state snapshot."""
    event_type: str
    summary: str
    ts: datetime
    impact_score: float
    source_id: str


class StructuredState(BaseModel):
    """Structured state object stored in state_snapshot.state_json."""
    ticker: str
    open_events: List[OpenEvent] = Field(default_factory=list)
    recent_catalysts: List[RecentCatalyst] = Field(default_factory=list)
    key_risks: List[str] = Field(default_factory=list)
    last_updated: datetime


# ============ API Response Models ============
class IngestResponse(BaseModel):
    """Response from /ingest_news endpoint."""
    news_id: str
    tickers: List[str]
    status: str


class AnalyzeResponse(BaseModel):
    """Response from /analyze_news/{news_id} endpoint."""
    news_id: str
    ticker: str
    analysis: LLMImpactAnalysis
    audit_id: int


class StateResponse(BaseModel):
    """Response from /state/{ticker} endpoint."""
    ticker: str
    state: StructuredState


# ============ Signal Engine Models ============
class SignalType(str, Enum):
    """Trading signal type."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalResult(BaseModel):
    """Output from the rule-based signal engine."""
    id: Optional[int] = None
    ticker: str
    signal: SignalType
    strength: float = Field(..., ge=0.0, le=1.0)
    impact_score: float = Field(..., ge=-1.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    event_type: str
    reasons: List[str] = Field(default_factory=list)
    news_impact_summary: str
    news_id: str
    audit_id: Optional[int] = None
    timestamp: datetime
