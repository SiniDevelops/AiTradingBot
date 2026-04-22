"""
Rule-Based Signal Engine for trading signal generation.

Derives BUY / SELL / HOLD signals from LLM impact analysis outputs
using transparent, deterministic rules. No black-box decisions —
every signal includes explicit reasoning.
"""
from datetime import datetime
from typing import List, Optional, Tuple
from app.models import LLMImpactAnalysis, SignalResult, SignalType


# ============ Configurable Thresholds ============
class SignalThresholds:
    """Configurable thresholds for signal generation."""

    # Impact score thresholds
    BUY_IMPACT_MIN = 0.3         # impact_score > this → candidate BUY
    SELL_IMPACT_MAX = -0.3       # impact_score < this → candidate SELL
    STRONG_IMPACT = 0.6          # abs(impact_score) > this → STRONG signal

    # Confidence thresholds
    MIN_CONFIDENCE = 0.6         # Below this → always HOLD
    HIGH_CONFIDENCE = 0.8        # Above this → boost signal strength

    # Severity weights (multiplier on signal strength)
    SEVERITY_WEIGHTS = {
        "high": 1.0,
        "med": 0.7,
        "low": 0.4,
    }

    # Risk flags that BLOCK a signal (force HOLD)
    BLOCKING_RISK_FLAGS = {"rumor", "low_quality_source"}

    # Risk flags that WEAKEN a signal (reduce strength)
    WEAKENING_RISK_FLAGS = {"ambiguous", "already_priced_in"}

    # Contradiction flags that BLOCK a signal
    BLOCKING_CONTRADICTION_FLAGS = {"conflicts_with_guidance", "conflicts_with_state"}

    # Event type bias adjustments
    EVENT_TYPE_BIAS = {
        "earnings": 0.0,         # Neutral — let impact_score speak
        "guidance": 0.05,        # Slight positive bias (forward-looking)
        "product_launch": 0.05,  # Slight positive bias
        "lawsuit": -0.05,        # Slight negative bias
        "regulatory": -0.05,     # Slight negative bias
        "macro": 0.0,            # Neutral
        "other": 0.0,            # Neutral
    }


class SignalEngine:
    """
    Deterministic signal engine that converts LLM analysis into trading signals.

    The engine applies the following rule chain:
    1. Check quality gates (confidence, risk_flags, contradiction_flags)
    2. Calculate adjusted impact score (event_type bias)
    3. Determine signal direction (BUY / SELL / HOLD)
    4. Calculate signal strength (0.0 to 1.0)
    5. Collect reasoning for full transparency
    """

    def __init__(self, thresholds: Optional[SignalThresholds] = None):
        self.thresholds = thresholds or SignalThresholds()

    def generate_signal(
        self,
        analysis: LLMImpactAnalysis,
        news_id: str,
        audit_id: Optional[int] = None,
        market_context=None,
    ) -> SignalResult:
        """
        Generate a trading signal from an LLM impact analysis,
        optionally enriched with real market data.

        Args:
            analysis: The structured analysis output from the LLM
            news_id: ID of the source news article
            audit_id: Optional audit trail ID
            market_context: Optional MarketContext with price/RSI/SMA data

        Returns:
            SignalResult with signal type, strength, and reasoning
        """
        reasons: List[str] = []
        t = self.thresholds

        # ── Step 1: Quality Gates ──────────────────────────────────
        blocked, block_reasons = self._check_quality_gates(analysis)
        if blocked:
            reasons.extend(block_reasons)
            return self._build_result(
                analysis=analysis,
                signal=SignalType.HOLD,
                strength=0.0,
                reasons=reasons,
                news_id=news_id,
                audit_id=audit_id,
            )

        # ── Step 2: Adjusted Impact Score ──────────────────────────
        event_bias = t.EVENT_TYPE_BIAS.get(analysis.event_type, 0.0)
        adjusted_impact = analysis.impact_score + event_bias

        if event_bias != 0.0:
            reasons.append(
                f"Event type '{analysis.event_type}' applied bias of {event_bias:+.2f} "
                f"(raw={analysis.impact_score:.2f} -> adjusted={adjusted_impact:.2f})"
            )
        else:
            reasons.append(f"Impact score: {analysis.impact_score:.2f} (no event-type bias)")

        # ── Step 2b: Market Data Adjustments ───────────────────────
        adjusted_impact, market_reasons = self._apply_market_adjustments(
            adjusted_impact, analysis, market_context
        )
        reasons.extend(market_reasons)

        # ── Step 3: Signal Direction ───────────────────────────────
        signal, direction_reasons = self._determine_direction(adjusted_impact, analysis)
        reasons.extend(direction_reasons)

        # ── Step 4: Signal Strength ────────────────────────────────
        strength, strength_reasons = self._calculate_strength(
            adjusted_impact, analysis, signal
        )
        reasons.extend(strength_reasons)

        # ── Step 5: Weakness Adjustments (only for BUY/SELL) ─────
        strength, weakness_reasons = self._apply_weakness_adjustments(
            strength, analysis, signal
        )
        reasons.extend(weakness_reasons)

        return self._build_result(
            analysis=analysis,
            signal=signal,
            strength=round(strength, 3),
            reasons=reasons,
            news_id=news_id,
            audit_id=audit_id,
        )

    # ────────────────────────────────────────────────────────────────
    # Internal rule methods
    # ────────────────────────────────────────────────────────────────

    def _check_quality_gates(
        self, analysis: LLMImpactAnalysis
    ) -> Tuple[bool, List[str]]:
        """Check confidence, risk flags, and contradiction flags."""
        reasons: List[str] = []
        t = self.thresholds

        # Gate 1: Minimum confidence
        if analysis.confidence < t.MIN_CONFIDENCE:
            reasons.append(
                f"HOLD: Confidence {analysis.confidence:.2f} below minimum "
                f"threshold {t.MIN_CONFIDENCE:.2f}"
            )
            return True, reasons

        # Gate 2: Blocking risk flags
        blocking_risks = set(analysis.risk_flags) & t.BLOCKING_RISK_FLAGS
        if blocking_risks:
            reasons.append(
                f"HOLD: Blocked by risk flag(s): {', '.join(blocking_risks)}"
            )
            return True, reasons

        # Gate 3: Blocking contradiction flags
        contradiction_set = set(analysis.contradiction_flags) - {"none"}
        blocking_contradictions = contradiction_set & t.BLOCKING_CONTRADICTION_FLAGS
        if blocking_contradictions:
            reasons.append(
                f"HOLD: Blocked by contradiction flag(s): "
                f"{', '.join(blocking_contradictions)}"
            )
            return True, reasons

        return False, reasons

    def _determine_direction(
        self, adjusted_impact: float, analysis: LLMImpactAnalysis
    ) -> Tuple[SignalType, List[str]]:
        """Determine BUY / SELL / HOLD based on adjusted impact."""
        reasons: List[str] = []
        t = self.thresholds

        if adjusted_impact > t.BUY_IMPACT_MIN:
            reasons.append(
                f"BUY: Adjusted impact {adjusted_impact:.2f} > "
                f"buy threshold {t.BUY_IMPACT_MIN:.2f}"
            )
            return SignalType.BUY, reasons

        elif adjusted_impact < t.SELL_IMPACT_MAX:
            reasons.append(
                f"SELL: Adjusted impact {adjusted_impact:.2f} < "
                f"sell threshold {t.SELL_IMPACT_MAX:.2f}"
            )
            return SignalType.SELL, reasons

        else:
            reasons.append(
                f"HOLD: Adjusted impact {adjusted_impact:.2f} within neutral zone "
                f"[{t.SELL_IMPACT_MAX:.2f}, {t.BUY_IMPACT_MIN:.2f}]"
            )
            return SignalType.HOLD, reasons

    def _calculate_strength(
        self,
        adjusted_impact: float,
        analysis: LLMImpactAnalysis,
        signal: SignalType,
    ) -> Tuple[float, List[str]]:
        """Calculate signal strength from 0.0 to 1.0."""
        reasons: List[str] = []
        t = self.thresholds

        if signal == SignalType.HOLD:
            return 0.0, reasons

        # Base strength from impact magnitude (0 to 1)
        base_strength = min(abs(adjusted_impact), 1.0)

        # Severity multiplier
        severity_weight = t.SEVERITY_WEIGHTS.get(analysis.severity, 0.5)
        weighted_strength = base_strength * severity_weight
        reasons.append(
            f"Strength: base={base_strength:.2f} × severity_{analysis.severity}"
            f"={severity_weight:.1f} → {weighted_strength:.2f}"
        )

        # Confidence boost
        if analysis.confidence >= t.HIGH_CONFIDENCE:
            boost = 0.1
            weighted_strength = min(1.0, weighted_strength + boost)
            reasons.append(
                f"High confidence boost (+{boost:.2f}): "
                f"confidence {analysis.confidence:.2f} ≥ {t.HIGH_CONFIDENCE:.2f}"
            )

        # Strong impact label
        if abs(adjusted_impact) > t.STRONG_IMPACT:
            reasons.append(f"STRONG signal: |impact| {abs(adjusted_impact):.2f} > {t.STRONG_IMPACT:.2f}")

        return weighted_strength, reasons

    def _apply_weakness_adjustments(
        self, strength: float, analysis: LLMImpactAnalysis, signal: SignalType
    ) -> Tuple[float, List[str]]:
        """Apply weakness adjustments for non-blocking risk flags (BUY/SELL only)."""
        reasons: List[str] = []

        # Skip adjustments for HOLD signals -- strength stays at 0.0
        if signal == SignalType.HOLD:
            return strength, reasons

        t = self.thresholds

        weakening_risks = set(analysis.risk_flags) & t.WEAKENING_RISK_FLAGS
        if weakening_risks:
            penalty = 0.15 * len(weakening_risks)
            strength = max(0.0, strength - penalty)
            reasons.append(
                f"Weakness penalty (-{penalty:.2f}) from: "
                f"{', '.join(weakening_risks)}"
            )

        # New information boost
        if analysis.is_new_information:
            boost = 0.05
            strength = min(1.0, strength + boost)
            reasons.append(f"New information boost (+{boost:.2f})")

        return strength, reasons

    def _apply_market_adjustments(
        self,
        adjusted_impact: float,
        analysis: LLMImpactAnalysis,
        market_context,
    ) -> Tuple[float, List[str]]:
        """
        Adjust the impact score based on real market data.

        Rules:
        - RSI oversold (<30) + positive news -> boost BUY
        - RSI overbought (>70) + negative news -> boost SELL
        - RSI overbought (>70) + positive news -> weaken (already priced in)
        - SMA bullish crossover -> small BUY bias
        - SMA bearish crossover -> small SELL bias
        - Near 52-week low + positive news -> boost BUY (reversal)
        - Near 52-week high + negative news -> boost SELL (top)
        - High volume -> amplify signal
        """
        reasons: List[str] = []

        if market_context is None or not getattr(market_context, 'data_available', False):
            reasons.append("No market data available -- signal based on news only")
            return adjusted_impact, reasons

        mc = market_context
        original_impact = adjusted_impact

        reasons.append(
            f"Market: Rs.{mc.current_price:.2f} ({mc.day_change_pct:+.1f}%), "
            f"RSI={mc.rsi_14:.0f}, SMA={mc.sma_signal}"
        )

        # ── RSI adjustments ──
        if mc.rsi_14 < 30:
            # Oversold
            if adjusted_impact > 0:
                boost = 0.15
                adjusted_impact += boost
                reasons.append(
                    f"RSI oversold ({mc.rsi_14:.0f}<30) + positive news: "
                    f"BUY boost +{boost:.2f}"
                )
            elif adjusted_impact < 0:
                dampen = 0.10
                adjusted_impact += dampen  # make less negative
                reasons.append(
                    f"RSI oversold ({mc.rsi_14:.0f}<30): "
                    f"dampened SELL by +{dampen:.2f} (potential bounce)"
                )
        elif mc.rsi_14 > 70:
            # Overbought
            if adjusted_impact > 0:
                penalty = 0.10
                adjusted_impact -= penalty
                reasons.append(
                    f"RSI overbought ({mc.rsi_14:.0f}>70) + positive news: "
                    f"weakened by -{penalty:.2f} (may be priced in)"
                )
            elif adjusted_impact < 0:
                boost = 0.15
                adjusted_impact -= boost  # make more negative
                reasons.append(
                    f"RSI overbought ({mc.rsi_14:.0f}>70) + negative news: "
                    f"SELL boost -{boost:.2f}"
                )

        # ── SMA crossover adjustments ──
        if mc.sma_signal == "bullish":
            bias = 0.05
            adjusted_impact += bias
            reasons.append(f"SMA-9 > SMA-21 (bullish trend): bias +{bias:.2f}")
        elif mc.sma_signal == "bearish":
            bias = -0.05
            adjusted_impact += bias
            reasons.append(f"SMA-9 < SMA-21 (bearish trend): bias {bias:.2f}")

        # ── 52-week proximity ──
        if mc.near_52w_low and adjusted_impact > 0:
            boost = 0.10
            adjusted_impact += boost
            reasons.append(
                f"Near 52-week low (Rs.{mc.week_52_low:.0f}): "
                f"reversal boost +{boost:.2f}"
            )
        elif mc.near_52w_high and adjusted_impact < 0:
            boost = 0.10
            adjusted_impact -= boost
            reasons.append(
                f"Near 52-week high (Rs.{mc.week_52_high:.0f}): "
                f"top risk boost -{boost:.2f}"
            )

        # ── Volume amplification ──
        if mc.volume_ratio > 2.0:
            amplify = 0.05
            if adjusted_impact > 0:
                adjusted_impact += amplify
            elif adjusted_impact < 0:
                adjusted_impact -= amplify
            reasons.append(
                f"High volume ({mc.volume_ratio:.1f}x avg): "
                f"signal amplified +/-{amplify:.2f}"
            )

        # Clamp to [-1.0, 1.0]
        adjusted_impact = max(-1.0, min(1.0, adjusted_impact))

        if adjusted_impact != original_impact:
            reasons.append(
                f"Market-adjusted impact: {original_impact:.2f} -> {adjusted_impact:.2f}"
            )

        return adjusted_impact, reasons

    def _build_result(
        self,
        analysis: LLMImpactAnalysis,
        signal: SignalType,
        strength: float,
        reasons: List[str],
        news_id: str,
        audit_id: Optional[int] = None,
    ) -> SignalResult:
        """Build the final SignalResult."""
        # Build news impact summary
        impact_summary = (
            f"{analysis.event_type.replace('_', ' ').title()} event for "
            f"{analysis.ticker}: impact={analysis.impact_score:+.2f}, "
            f"severity={analysis.severity}, confidence={analysis.confidence:.0%}, "
            f"horizon={analysis.horizon}"
        )

        return SignalResult(
            ticker=analysis.ticker,
            signal=signal,
            strength=strength,
            impact_score=analysis.impact_score,
            confidence=analysis.confidence,
            event_type=analysis.event_type,
            reasons=reasons,
            news_impact_summary=impact_summary,
            news_id=news_id,
            audit_id=audit_id,
            timestamp=datetime.now(),
        )


# ============ Module-level convenience ============
_engine: Optional[SignalEngine] = None


def get_signal_engine() -> SignalEngine:
    """Get or create the global signal engine instance."""
    global _engine
    if _engine is None:
        _engine = SignalEngine()
    return _engine
