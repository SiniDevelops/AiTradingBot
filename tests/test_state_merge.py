"""
Tests for state manager conflict resolution (Option B).
"""
import pytest
from datetime import datetime, timedelta
import json
import sqlite3
import os

from app import db
from app.models import LLMImpactAnalysis
from app.state_manager import StateManager

# Use test database
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "test_trading_bot.db")


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """Setup test database before each test."""
    # Use test database
    db.DB_PATH = TEST_DB_PATH
    
    # Remove existing test DB
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    # Initialize
    db.init_db()
    
    # Create default profile
    db.insert_or_update_profile("AAPL", "Apple Inc. - Technology company")
    
    yield
    
    # Cleanup after test
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


class TestStateEventCreation:
    """Test creation of new open events."""
    
    def test_new_open_event_creates_record(self):
        """Should create a new open event when none exists."""
        analysis = LLMImpactAnalysis(
            ticker="AAPL",
            event_type="earnings",
            is_new_information=True,
            impact_score=0.5,
            horizon="swing",
            severity="med",
            confidence=0.8,
            risk_flags=[],
            contradiction_flags=["none"],
            summary="Q3 earnings beat expectations",
            evidence="Apple reported 5% YoY growth",
            citations=[]
        )
        
        now = datetime.now()
        success, msg = StateManager.process_analysis(
            analysis=analysis,
            ticker="AAPL",
            source_id="news_001",
            published_at=now
        )
        
        assert success
        
        # Verify event was created
        events = db.get_state_events_by_ticker("AAPL", status="open")
        assert len(events) == 1
        assert events[0]["event_type"] == "earnings"
        assert events[0]["status"] == "open"
        assert events[0]["summary"] == "Q3 earnings beat expectations"


class TestEventUpdates:
    """Test updating existing open events with new information."""
    
    def test_same_type_newer_information_updates_event(self):
        """Should update existing open event with higher confidence info."""
        # Create initial event
        event_id_1 = db.insert_state_event(
            ticker="AAPL",
            event_type="lawsuit",
            status="open",
            severity="low",
            impact_score=-0.2,
            horizon="long",
            summary="Potential patent lawsuit",
            source_id="news_001",
            start_ts=datetime.now(),
            end_ts=None,
            confidence=0.5,
            evidence="Rumored lawsuit claim"
        )
        
        # New higher-confidence analysis
        analysis = LLMImpactAnalysis(
            ticker="AAPL",
            event_type="lawsuit",
            is_new_information=True,
            impact_score=-0.6,
            horizon="long",
            severity="high",
            confidence=0.85,
            risk_flags=["low_quality_source"],
            contradiction_flags=["none"],
            summary="Patent lawsuit filed against Apple in federal court",
            evidence="Court filing shows lawsuit is official",
            citations=[]
        )
        
        success, msg = StateManager.process_analysis(
            analysis=analysis,
            ticker="AAPL",
            source_id="news_002",
            published_at=datetime.now()
        )
        
        assert success
        
        # Verify original event was updated
        events = db.get_state_events_by_ticker("AAPL", status="open")
        assert len(events) >= 1
        
        # Find the updated event
        updated_event = next((e for e in events if e["event_type"] == "lawsuit"), None)
        assert updated_event is not None
        assert updated_event["confidence"] >= 0.85
        assert "federal court" in updated_event["summary"]


class TestEventClosure:
    """Test closing of resolved events."""
    
    def test_resolution_news_closes_open_event(self):
        """Should close open event when resolution is detected."""
        # Create initial open event
        event_id = db.insert_state_event(
            ticker="AAPL",
            event_type="lawsuit",
            status="open",
            severity="high",
            impact_score=-0.7,
            horizon="long",
            summary="Patent lawsuit filed",
            source_id="news_001",
            start_ts=datetime.now() - timedelta(days=30),
            end_ts=None,
            confidence=0.9,
            evidence="Court filing"
        )
        
        # Resolution analysis
        analysis = LLMImpactAnalysis(
            ticker="AAPL",
            event_type="lawsuit",
            is_new_information=True,
            impact_score=0.1,  # Reduced impact when resolved
            horizon="long",
            severity="low",
            confidence=0.8,
            risk_flags=[],
            contradiction_flags=["none"],
            summary="Patent lawsuit resolved - settled out of court",
            evidence="Settlement agreement signed",
            citations=[]
        )
        
        success, msg = StateManager.process_analysis(
            analysis=analysis,
            ticker="AAPL",
            source_id="news_002",
            published_at=datetime.now()
        )
        
        assert success
        
        # Verify original event is closed
        open_events = db.get_state_events_by_ticker("AAPL", status="open")
        lawsuits_open = [e for e in open_events if e["event_type"] == "lawsuit"]
        assert len(lawsuits_open) == 0
        
        # Verify closed events exist
        closed_events = db.get_state_events_by_ticker("AAPL", status="closed")
        lawsuits_closed = [e for e in closed_events if e["event_type"] == "lawsuit"]
        assert len(lawsuits_closed) > 0


class TestIdempotency:
    """Test idempotency of state updates."""
    
    def test_analyzing_same_news_twice_is_idempotent(self):
        """Should not duplicate events when analyzing same news twice."""
        analysis = LLMImpactAnalysis(
            ticker="AAPL",
            event_type="product_launch",
            is_new_information=True,
            impact_score=0.7,
            horizon="swing",
            severity="high",
            confidence=0.9,
            risk_flags=[],
            contradiction_flags=["none"],
            summary="New iPhone 15 Pro launch announced",
            evidence="Apple announced iPhone 15 Pro",
            citations=[]
        )
        
        now = datetime.now()
        
        # First analysis
        success1, msg1 = StateManager.process_analysis(
            analysis=analysis,
            ticker="AAPL",
            source_id="news_001",
            published_at=now
        )
        assert success1
        
        # Second analysis of same news
        success2, msg2 = StateManager.process_analysis(
            analysis=analysis,
            ticker="AAPL",
            source_id="news_001",
            published_at=now
        )
        assert not success2  # Should fail due to idempotency
        
        # Verify only one event exists
        events = db.get_state_events_by_ticker("AAPL")
        product_launches = [e for e in events if e["event_type"] == "product_launch"]
        assert len(product_launches) == 1


class TestStateSnapshot:
    """Test state snapshot building and persistence."""
    
    def test_rebuild_state_snapshot_aggregates_events(self):
        """Should rebuild snapshot with open events and recent catalysts."""
        # Create mix of events
        now = datetime.now()
        
        open_event_id = db.insert_state_event(
            ticker="AAPL",
            event_type="earnings",
            status="open",
            severity="med",
            impact_score=0.4,
            horizon="swing",
            summary="Q3 earnings announcement pending",
            source_id="news_001",
            start_ts=now,
            end_ts=None,
            confidence=0.7,
            evidence="Scheduled earnings date"
        )
        
        closed_event_id = db.insert_state_event(
            ticker="AAPL",
            event_type="product_launch",
            status="closed",
            severity="high",
            impact_score=0.8,
            horizon="long",
            summary="New Apple Watch launched",
            source_id="news_002",
            start_ts=now - timedelta(days=10),
            end_ts=now - timedelta(days=5),
            confidence=0.9,
            evidence="Product announcement and reviews"
        )
        
        # Rebuild snapshot
        state = StateManager.rebuild_state_snapshot("AAPL")
        
        # Verify aggregation
        assert state.ticker == "AAPL"
        assert len(state.open_events) == 1
        assert state.open_events[0].event_type == "earnings"
        assert len(state.recent_catalysts) == 1
        assert state.recent_catalysts[0].event_type == "product_launch"
        assert len(state.key_risks) > 0
    
    def test_state_snapshot_persisted_and_retrieved(self):
        """Should persist snapshot and retrieve it correctly."""
        # Build and commit snapshot
        state = StateManager.commit_state_snapshot("AAPL")
        
        # Retrieve it
        retrieved_state = StateManager.get_current_state("AAPL")
        
        assert retrieved_state is not None
        assert retrieved_state.ticker == "AAPL"
        assert retrieved_state.model_dump() == state.model_dump()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
