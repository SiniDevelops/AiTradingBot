"""
State manager implementing Option B: deterministic merge/update with LLM assistance.
Handles conflict resolution for company state updates.
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from app.models import (
    LLMImpactAnalysis,
    StateEvent,
    StructuredState,
    OpenEvent,
    RecentCatalyst
)
from app.db import (
    insert_state_event,
    get_state_events_by_ticker,
    update_state_event,
    find_similar_open_events,
    insert_or_update_snapshot,
    get_snapshot,
)
from app.utils import similarity_score


class StateManager:
    """Manages company state with conflict resolution (Option B)."""
    
    # Idempotency guard: (ticker, event_type, source_id) -> event_id
    _event_guard = {}
    
    @staticmethod
    def dedupe_key(ticker: str, event_type: str, source_id: str) -> str:
        """Create deduplication key."""
        return f"{ticker}:{event_type}:{source_id}"
    
    @staticmethod
    def process_analysis(analysis: LLMImpactAnalysis,
                        ticker: str,
                        source_id: str,
                        published_at: datetime) -> Tuple[bool, str]:
        """
        Process LLM analysis and update state deterministically.
        
        Returns:
            (success: bool, message: str)
        """
        # Check idempotency
        guard_key = StateManager.dedupe_key(ticker, analysis.event_type, source_id)
        if guard_key in StateManager._event_guard:
            print(f"Duplicate analysis for {guard_key}, skipping")
            return False, "Duplicate analysis"
        
        # Determine if this event should close any existing events
        should_close_existing = StateManager._should_close_event(analysis, ticker)
        
        # Find similar open events
        similar_events = find_similar_open_events(
            ticker=ticker,
            event_type=analysis.event_type,
            summary=analysis.summary
        )
        
        if similar_events and not should_close_existing:
            # Update existing event with new information
            event = similar_events[0]
            StateManager._update_existing_event(
                event_id=event["id"],
                analysis=analysis,
                confidence_threshold=0.6
            )
            StateManager._event_guard[guard_key] = event["id"]
            return True, f"Updated existing event {event['id']}"
        
        elif should_close_existing and similar_events:
            # Close the existing event(s)
            for event in similar_events:
                update_state_event(
                    event_id=event["id"],
                    status="closed",
                    end_ts=published_at
                )
            
            # Record the closing summary
            summary = f"[RESOLVED] {analysis.summary}"
            event_id = insert_state_event(
                ticker=ticker,
                event_type=analysis.event_type,
                status="closed",
                severity=analysis.severity,
                impact_score=analysis.impact_score,
                horizon=analysis.horizon,
                summary=summary,
                source_id=source_id,
                start_ts=published_at,
                end_ts=published_at,
                confidence=analysis.confidence,
                evidence=analysis.evidence
            )
            StateManager._event_guard[guard_key] = event_id
            return True, f"Closed event with new resolution {event_id}"
        
        else:
            # Create new open event
            event_id = insert_state_event(
                ticker=ticker,
                event_type=analysis.event_type,
                status="open",
                severity=analysis.severity,
                impact_score=analysis.impact_score,
                horizon=analysis.horizon,
                summary=analysis.summary,
                source_id=source_id,
                start_ts=published_at,
                end_ts=None,  # Open event has no end
                confidence=analysis.confidence,
                evidence=analysis.evidence
            )
            StateManager._event_guard[guard_key] = event_id
            return True, f"Created new event {event_id}"
    
    @staticmethod
    def _should_close_event(analysis: LLMImpactAnalysis, ticker: str) -> bool:
        """
        Determine if this analysis indicates closure of existing events.
        Based on contradiction_flags and event_type semantics.
        """
        # Check explicit contradiction signals
        if "conflicts_with_guidance" in analysis.contradiction_flags:
            return False  # Contradiction doesn't close; it opens an issue
        
        # Check for resolution keywords in summary
        resolution_keywords = ["resolved", "settled", "closed", "resolved", "dismissed", "ended", "concluded"]
        if any(kw in analysis.summary.lower() for kw in resolution_keywords):
            return True
        
        # Check for status-indicating event types
        if analysis.event_type in ["earnings", "guidance"]:
            # These update rather than close previous events
            return False
        
        return False
    
    @staticmethod
    def _update_existing_event(event_id: int,
                               analysis: LLMImpactAnalysis,
                               confidence_threshold: float = 0.6):
        """
        Update an existing open event with new analysis if confidence is higher.
        """
        from app.db import get_db
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT confidence FROM state_events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            old_confidence = row[0] if row else 0.0
        
        # Only update if new analysis has higher confidence
        if analysis.confidence >= old_confidence:
            update_state_event(
                event_id=event_id,
                severity=analysis.severity,
                impact_score=analysis.impact_score,
                horizon=analysis.horizon,
                summary=analysis.summary,
                confidence=analysis.confidence,
                evidence=analysis.evidence
            )
    
    @staticmethod
    def rebuild_state_snapshot(ticker: str, look_back_events: int = 50) -> StructuredState:
        """
        Rebuild state snapshot from recent events.
        
        Aggregates:
        - Open events (current issues)
        - Recent catalysts (last 10 impactful closed events)
        - Key risks (derived from open events)
        """
        # Get all recent events
        all_events = get_state_events_by_ticker(ticker)
        recent_events = all_events[:look_back_events]
        
        # Separate open and closed
        open_events = [e for e in recent_events if e["status"] == "open"]
        closed_events = [e for e in recent_events if e["status"] == "closed"]
        
        # Build open_events list
        open_events_list = [
            OpenEvent(
                event_type=e["event_type"],
                summary=e["summary"],
                start_ts=datetime.fromisoformat(e["start_ts"]) if isinstance(e["start_ts"], str) else e["start_ts"],
                severity=e["severity"],
                impact_score=e["impact_score"],
                horizon=e["horizon"],
                confidence=e["confidence"],
                source_id=e["source_id"]
            )
            for e in open_events
        ]
        
        # Build recent_catalysts list (last 10 closed events)
        recent_catalysts_list = [
            RecentCatalyst(
                event_type=e["event_type"],
                summary=e["summary"],
                ts=datetime.fromisoformat(e["end_ts"]) if isinstance(e["end_ts"], str) else e["end_ts"],
                impact_score=e["impact_score"],
                source_id=e["source_id"]
            )
            for e in closed_events[:10]
        ]
        
        # Build key_risks from open events
        key_risks = []
        for event in open_events_list:
            if event.severity in ["high", "med"]:
                risk_text = f"[{event.severity.upper()}] {event.event_type}: {event.summary}"
                key_risks.append(risk_text)
        
        state = StructuredState(
            ticker=ticker,
            open_events=open_events_list,
            recent_catalysts=recent_catalysts_list,
            key_risks=key_risks,
            last_updated=datetime.now()
        )
        
        return state
    
    @staticmethod
    def commit_state_snapshot(ticker: str):
        """Rebuild and persist state snapshot for a ticker."""
        state = StateManager.rebuild_state_snapshot(ticker)
        state_json = state.model_dump_json()
        insert_or_update_snapshot(ticker, state_json)
        return state
    
    @staticmethod
    def get_current_state(ticker: str) -> Optional[StructuredState]:
        """Retrieve current state for a ticker."""
        snapshot = get_snapshot(ticker)
        if not snapshot:
            return None
        
        try:
            state_dict = json.loads(snapshot["state_json"])
            return StructuredState(**state_dict)
        except (json.JSONDecodeError, ValueError):
            return None
