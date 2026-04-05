"""
Tests for the rule-based signal engine.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.models import LLMImpactAnalysis, SignalType
from app.signal_engine import SignalEngine, SignalThresholds


def make_analysis(
    ticker="AAPL",
    event_type="earnings",
    impact_score=0.5,
    severity="med",
    confidence=0.8,
    risk_flags=None,
    contradiction_flags=None,
    is_new_information=True,
    horizon="swing",
    summary="Test event",
    evidence="Test evidence",
):
    """Helper to create an LLMImpactAnalysis with defaults."""
    return LLMImpactAnalysis(
        ticker=ticker,
        event_type=event_type,
        is_new_information=is_new_information,
        impact_score=impact_score,
        horizon=horizon,
        severity=severity,
        confidence=confidence,
        risk_flags=risk_flags or [],
        contradiction_flags=contradiction_flags or ["none"],
        summary=summary,
        evidence=evidence,
        citations=[],
    )


class TestSignalDirection:
    """Tests for BUY / SELL / HOLD signal direction."""

    def test_buy_signal_on_positive_impact(self):
        """Positive impact above threshold should generate BUY."""
        engine = SignalEngine()
        analysis = make_analysis(impact_score=0.5, confidence=0.8)
        result = engine.generate_signal(analysis, news_id="test_001")

        assert result.signal == SignalType.BUY
        assert result.strength > 0

    def test_sell_signal_on_negative_impact(self):
        """Negative impact below threshold should generate SELL."""
        engine = SignalEngine()
        analysis = make_analysis(impact_score=-0.5, confidence=0.8)
        result = engine.generate_signal(analysis, news_id="test_002")

        assert result.signal == SignalType.SELL
        assert result.strength > 0

    def test_hold_on_neutral_impact(self):
        """Impact within neutral zone should generate HOLD."""
        engine = SignalEngine()
        analysis = make_analysis(impact_score=0.1, confidence=0.8)
        result = engine.generate_signal(analysis, news_id="test_003")

        assert result.signal == SignalType.HOLD
        assert result.strength == 0.0

    def test_hold_on_exactly_boundary(self):
        """Impact exactly at boundary (0.3) should be HOLD (not >)."""
        engine = SignalEngine()
        analysis = make_analysis(impact_score=0.3, confidence=0.8)
        result = engine.generate_signal(analysis, news_id="test_004")

        assert result.signal == SignalType.HOLD

    def test_buy_just_above_boundary(self):
        """Impact just above threshold should be BUY."""
        engine = SignalEngine()
        analysis = make_analysis(impact_score=0.31, confidence=0.8)
        result = engine.generate_signal(analysis, news_id="test_005")

        assert result.signal == SignalType.BUY


class TestQualityGates:
    """Tests for quality gate blocking."""

    def test_hold_on_low_confidence(self):
        """Low confidence should force HOLD regardless of impact."""
        engine = SignalEngine()
        analysis = make_analysis(impact_score=0.9, confidence=0.4)
        result = engine.generate_signal(analysis, news_id="test_010")

        assert result.signal == SignalType.HOLD
        assert result.strength == 0.0
        assert any("Confidence" in r for r in result.reasons)

    def test_hold_on_rumor_risk_flag(self):
        """Rumor risk flag should block and force HOLD."""
        engine = SignalEngine()
        analysis = make_analysis(
            impact_score=0.8, confidence=0.9, risk_flags=["rumor"]
        )
        result = engine.generate_signal(analysis, news_id="test_011")

        assert result.signal == SignalType.HOLD
        assert any("rumor" in r for r in result.reasons)

    def test_hold_on_low_quality_source(self):
        """Low quality source flag should block and force HOLD."""
        engine = SignalEngine()
        analysis = make_analysis(
            impact_score=0.8, confidence=0.9, risk_flags=["low_quality_source"]
        )
        result = engine.generate_signal(analysis, news_id="test_012")

        assert result.signal == SignalType.HOLD

    def test_hold_on_contradiction_with_guidance(self):
        """Contradiction with guidance should block."""
        engine = SignalEngine()
        analysis = make_analysis(
            impact_score=0.8, confidence=0.9,
            contradiction_flags=["conflicts_with_guidance"]
        )
        result = engine.generate_signal(analysis, news_id="test_013")

        assert result.signal == SignalType.HOLD
        assert any("contradiction" in r.lower() for r in result.reasons)

    def test_hold_on_contradiction_with_state(self):
        """Contradiction with state should block."""
        engine = SignalEngine()
        analysis = make_analysis(
            impact_score=0.8, confidence=0.9,
            contradiction_flags=["conflicts_with_state"]
        )
        result = engine.generate_signal(analysis, news_id="test_014")

        assert result.signal == SignalType.HOLD

    def test_none_contradiction_does_not_block(self):
        """'none' contradiction flag should not block."""
        engine = SignalEngine()
        analysis = make_analysis(
            impact_score=0.5, confidence=0.8,
            contradiction_flags=["none"]
        )
        result = engine.generate_signal(analysis, news_id="test_015")

        assert result.signal == SignalType.BUY


class TestStrength:
    """Tests for signal strength calculation."""

    def test_strength_scales_with_severity(self):
        """Higher severity should produce higher strength."""
        engine = SignalEngine()

        high = engine.generate_signal(
            make_analysis(impact_score=0.6, severity="high", confidence=0.7),
            news_id="str_001"
        )
        med = engine.generate_signal(
            make_analysis(impact_score=0.6, severity="med", confidence=0.7),
            news_id="str_002"
        )
        low = engine.generate_signal(
            make_analysis(impact_score=0.6, severity="low", confidence=0.7),
            news_id="str_003"
        )

        assert high.strength > med.strength > low.strength

    def test_high_confidence_boost(self):
        """Confidence >= 0.8 should add strength boost."""
        engine = SignalEngine()

        high_conf = engine.generate_signal(
            make_analysis(impact_score=0.5, confidence=0.85, is_new_information=False),
            news_id="conf_001"
        )
        normal_conf = engine.generate_signal(
            make_analysis(impact_score=0.5, confidence=0.7, is_new_information=False),
            news_id="conf_002"
        )

        assert high_conf.strength > normal_conf.strength

    def test_new_information_boosts_strength(self):
        """New information flag should add small strength boost."""
        engine = SignalEngine()

        new_info = engine.generate_signal(
            make_analysis(impact_score=0.5, confidence=0.7, is_new_information=True),
            news_id="new_001"
        )
        old_info = engine.generate_signal(
            make_analysis(impact_score=0.5, confidence=0.7, is_new_information=False),
            news_id="new_002"
        )

        assert new_info.strength > old_info.strength

    def test_ambiguous_flag_reduces_strength(self):
        """Ambiguous risk flag should reduce strength (not block)."""
        engine = SignalEngine()

        clean = engine.generate_signal(
            make_analysis(impact_score=0.5, confidence=0.8, risk_flags=[]),
            news_id="amb_001"
        )
        ambiguous = engine.generate_signal(
            make_analysis(impact_score=0.5, confidence=0.8, risk_flags=["ambiguous"]),
            news_id="amb_002"
        )

        assert ambiguous.signal == SignalType.BUY  # Not blocked
        assert ambiguous.strength < clean.strength   # But weaker

    def test_hold_signal_has_zero_strength(self):
        """HOLD signals should always have 0 strength."""
        engine = SignalEngine()
        result = engine.generate_signal(
            make_analysis(impact_score=0.1, confidence=0.8),
            news_id="hold_001"
        )

        assert result.signal == SignalType.HOLD
        assert result.strength == 0.0


class TestEventTypeBias:
    """Tests for event type bias adjustment."""

    def test_lawsuit_negative_bias(self):
        """Lawsuit events should have slight negative bias."""
        engine = SignalEngine()

        # Impact of -0.28 alone would be HOLD (-0.28 > -0.30)
        # With lawsuit bias of -0.05, adjusted = -0.33 → SELL
        result = engine.generate_signal(
            make_analysis(impact_score=-0.28, event_type="lawsuit", confidence=0.8),
            news_id="bias_001"
        )

        assert result.signal == SignalType.SELL

    def test_product_launch_positive_bias(self):
        """Product launch events should have slight positive bias."""
        engine = SignalEngine()

        # Impact of 0.28 alone would be HOLD
        # With product_launch bias of +0.05, adjusted = 0.33 → BUY
        result = engine.generate_signal(
            make_analysis(impact_score=0.28, event_type="product_launch", confidence=0.8),
            news_id="bias_002"
        )

        assert result.signal == SignalType.BUY

    def test_earnings_no_bias(self):
        """Earnings events should have zero bias."""
        engine = SignalEngine()

        # Impact of 0.29 with 0 bias stays at 0.29 → HOLD
        result = engine.generate_signal(
            make_analysis(impact_score=0.29, event_type="earnings", confidence=0.8),
            news_id="bias_003"
        )

        assert result.signal == SignalType.HOLD


class TestSignalResultCompleteness:
    """Tests that SignalResult has all required fields."""

    def test_all_fields_populated(self):
        """Every signal should have all fields populated."""
        engine = SignalEngine()
        result = engine.generate_signal(
            make_analysis(impact_score=0.6, confidence=0.8),
            news_id="fields_001",
            audit_id=42,
        )

        assert result.ticker == "AAPL"
        assert result.signal in (SignalType.BUY, SignalType.SELL, SignalType.HOLD)
        assert 0.0 <= result.strength <= 1.0
        assert -1.0 <= result.impact_score <= 1.0
        assert 0.0 <= result.confidence <= 1.0
        assert result.event_type == "earnings"
        assert isinstance(result.reasons, list)
        assert len(result.reasons) > 0
        assert result.news_impact_summary != ""
        assert result.news_id == "fields_001"
        assert result.audit_id == 42
        assert result.timestamp is not None

    def test_reasons_always_populated(self):
        """Reasons list should never be empty."""
        engine = SignalEngine()

        # Test for each signal type
        for impact in [0.6, -0.6, 0.1]:
            result = engine.generate_signal(
                make_analysis(impact_score=impact, confidence=0.8),
                news_id=f"reasons_{impact}"
            )
            assert len(result.reasons) > 0, f"Empty reasons for impact={impact}"

    def test_news_impact_summary_contains_ticker(self):
        """Summary should mention the ticker."""
        engine = SignalEngine()
        result = engine.generate_signal(
            make_analysis(ticker="MSFT", impact_score=0.5),
            news_id="summary_001"
        )

        assert "MSFT" in result.news_impact_summary
