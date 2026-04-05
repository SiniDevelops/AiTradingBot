# Trading Conditions & Signal Generation Rules

This document explains exactly **how and when** the trading bot generates BUY, SELL, or HOLD signals, and how news analysis drives those decisions.

---

## 1. System Data Flow

```
  News Article
       |
       v
  [1] INGESTION ─── Clean text, hash for dedup, store raw + clean
       |
       v
  [2] TICKER LINKING ─── Extract tickers via patterns ($AAPL, company names)
       |
       v
  [3] RAG RETRIEVAL ─── Retrieve relevant context (profile, state, events) via FAISS
       |
       v
  [4] LLM ANALYSIS ─── Generate structured impact assessment (JSON)
       |
       v
  [5] STATE MANAGEMENT ─── Update company state (events, snapshots)
       |
       v
  [6] SIGNAL ENGINE ─── Apply rules to LLM output → BUY / SELL / HOLD
       |
       v
  [Signal stored in DB + shown on dashboard]
```

---

## 2. LLM Analysis Output Fields

The LLM analyzer produces a structured `LLMImpactAnalysis` object. These fields are the inputs to the signal engine:

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `ticker` | string | — | Stock ticker symbol (e.g., AAPL) |
| `event_type` | enum | lawsuit, earnings, guidance, product_launch, regulatory, macro, other | Category of the news event |
| `is_new_information` | bool | — | Whether this news is genuinely new (not previously covered) |
| `impact_score` | float | -1.0 to +1.0 | Estimated price impact. Positive = bullish, Negative = bearish |
| `horizon` | enum | intraday, swing, long | Expected time horizon of the impact |
| `severity` | enum | low, med, high | How significant the event is |
| `confidence` | float | 0.0 to 1.0 | LLM's confidence in its own analysis |
| `risk_flags` | list | rumor, low_quality_source, ambiguous, already_priced_in | Quality concerns about the news |
| `contradiction_flags` | list | conflicts_with_guidance, conflicts_with_state, none | Whether this contradicts known data |
| `summary` | string | — | 1-2 sentence summary of the analysis |
| `evidence` | string | — | Key excerpt from the article |
| `citations` | list | — | References to retrieved context chunks |

---

## 3. Signal Generation Rules

The signal engine processes LLM output through a **5-step deterministic rule chain**. Every decision is recorded with explicit reasoning.

### 3.1 Step 1: Quality Gates (Checked First)

These gates must ALL pass. If any gate fails, the signal is forced to **HOLD** regardless of impact score.

| Gate | Condition | Result |
|------|-----------|--------|
| **Confidence Gate** | `confidence < 0.6` | → **HOLD** ("Confidence below minimum threshold") |
| **Risk Flag Gate** | `risk_flags` contains `"rumor"` OR `"low_quality_source"` | → **HOLD** ("Blocked by risk flag") |
| **Contradiction Gate** | `contradiction_flags` contains `"conflicts_with_guidance"` OR `"conflicts_with_state"` | → **HOLD** ("Blocked by contradiction flag") |

**Rationale**: We never generate a BUY or SELL signal on low-confidence, rumored, or contradictory information.

### 3.2 Step 2: Impact Score Adjustment

The raw `impact_score` is adjusted by a small event-type bias:

| Event Type | Bias | Rationale |
|-----------|------|-----------|
| `earnings` | 0.00 | Neutral — earnings speak for themselves |
| `guidance` | +0.05 | Slight positive — forward-looking statements carry weight |
| `product_launch` | +0.05 | Slight positive — launches signal innovation |
| `lawsuit` | -0.05 | Slight negative — legal risk bias |
| `regulatory` | -0.05 | Slight negative — regulatory uncertainty |
| `macro` | 0.00 | Neutral — macro events are ambiguous |
| `other` | 0.00 | Neutral |

```
adjusted_impact = impact_score + event_type_bias
```

**Example**: A lawsuit event with `impact_score = -0.28` becomes `adjusted_impact = -0.33` (crosses the SELL threshold).

### 3.3 Step 3: Signal Direction

Based on the adjusted impact score:

| Condition | Signal |
|-----------|--------|
| `adjusted_impact > +0.3` | **BUY** |
| `adjusted_impact < -0.3` | **SELL** |
| `-0.3 ≤ adjusted_impact ≤ +0.3` | **HOLD** |

The neutral zone (`-0.3` to `+0.3`) prevents trading on weak or ambiguous signals.

### 3.4 Step 4: Signal Strength (0.0 to 1.0)

For BUY and SELL signals, strength quantifies conviction:

```
base_strength = min(|adjusted_impact|, 1.0)
```

**Severity multiplier**:
| Severity | Multiplier |
|----------|-----------|
| `high` | × 1.0 |
| `med` | × 0.7 |
| `low` | × 0.4 |

```
weighted_strength = base_strength × severity_multiplier
```

**High confidence boost**: If `confidence ≥ 0.8`, add +0.1 to strength (capped at 1.0).

**Strong signal label**: If `|adjusted_impact| > 0.6`, the signal is labeled as STRONG in the reasoning.

### 3.5 Step 5: Weakness Adjustments

Non-blocking risk flags reduce signal strength:

| Flag | Penalty |
|------|---------|
| `ambiguous` | -0.15 |
| `already_priced_in` | -0.15 |

These flags don't block the signal but reduce its strength.

**New information boost**: If `is_new_information = true`, add +0.05 to strength.

```
final_strength = max(0.0, weighted_strength - penalties + boosts)
```

---

## 4. How News Affects Trading Signals

### Example 1: Earnings Beat → BUY

```
Article: "Apple Beats Q1 2024 Earnings, Raises Guidance"
Ticker:  AAPL

LLM Output:
  event_type:    earnings
  impact_score:  +0.60
  severity:      med
  confidence:    0.65
  risk_flags:    []
  contradiction: [none]

Signal Engine Processing:
  1. Quality gates: PASS (confidence 0.65 ≥ 0.60, no risk flags, no contradictions)
  2. Adjusted impact: 0.60 + 0.00 (earnings bias) = 0.60
  3. Direction: 0.60 > 0.30 → BUY
  4. Strength: base=0.60 × severity_med=0.70 = 0.42
  5. New info boost: +0.05 → final strength = 0.47

Result: BUY (strength 0.47)
```

### Example 2: Regulatory Investigation → SELL

```
Article: "Google Faces Regulatory Scrutiny Over AI Search"
Ticker:  GOOGL

LLM Output:
  event_type:    regulatory
  impact_score:  -0.30
  severity:      med
  confidence:    0.65
  risk_flags:    []
  contradiction: [none]

Signal Engine Processing:
  1. Quality gates: PASS
  2. Adjusted impact: -0.30 + (-0.05) (regulatory bias) = -0.35
  3. Direction: -0.35 < -0.30 → SELL
  4. Strength: base=0.35 × severity_med=0.70 = 0.245
  5. New info boost: +0.05 → final strength = 0.295

Result: SELL (strength 0.30)
```

### Example 3: Low Confidence Rumor → HOLD

```
Article: "Rumor: Tesla May Announce Stock Split"
Ticker:  TSLA

LLM Output:
  event_type:    other
  impact_score:  +0.50
  severity:      med
  confidence:    0.40
  risk_flags:    [rumor]
  contradiction: [none]

Signal Engine Processing:
  1. Quality gates: FAIL
     - Confidence 0.40 < 0.60 threshold → BLOCKED
     - (Even if confidence passed, "rumor" risk flag would also block)

Result: HOLD (strength 0.00)
  Reasons: "Confidence 0.40 below minimum threshold 0.60"
```

### Example 4: Strong Positive with Ambiguity → Weakened BUY

```
Article: "Microsoft Announces $10B AI Partnership with OpenAI"
Ticker:  MSFT

LLM Output:
  event_type:    other
  impact_score:  +0.60
  severity:      med
  confidence:    0.70
  risk_flags:    [ambiguous]
  contradiction: [none]
  is_new_information: true

Signal Engine Processing:
  1. Quality gates: PASS (ambiguous is weakening, not blocking)
  2. Adjusted impact: 0.60 + 0.00 = 0.60
  3. Direction: 0.60 > 0.30 → BUY
  4. Strength: base=0.60 × severity_med=0.70 = 0.42
  5. Weakness: -0.15 (ambiguous) + 0.05 (new info) = -0.10
     Final strength: 0.42 - 0.10 = 0.32

Result: BUY (strength 0.32) — weaker due to ambiguity flag
```

---

## 5. Edge Cases

### Conflicting Signals for Same Ticker
If multiple news articles generate conflicting signals (e.g., BUY then SELL for AAPL), both signals are recorded independently. Each signal references its source news article. The dashboard shows all signals in chronological order so you can see the full history.

### Resolution Events
When a news article resolves a prior event (e.g., "Lawsuit Dismissed"), the state manager closes the open event. The signal engine still evaluates the resolution news independently — a lawsuit dismissal with positive impact would generate a BUY signal.

### Low Confidence Analysis
If the LLM outputs `confidence < 0.6`, the signal is always HOLD regardless of impact. This prevents acting on uncertain analysis.

### Already Priced In
If `risk_flags` includes `"already_priced_in"`, the signal is still generated (not blocked) but its strength is reduced by 0.15. This reflects that the expected price movement may be smaller.

---

## 6. Configuration Reference

All thresholds are defined in `app/signal_engine.py` in the `SignalThresholds` class:

```python
class SignalThresholds:
    BUY_IMPACT_MIN = 0.3         # impact_score > this → candidate BUY
    SELL_IMPACT_MAX = -0.3       # impact_score < this → candidate SELL
    STRONG_IMPACT = 0.6          # |impact_score| > this → STRONG label
    MIN_CONFIDENCE = 0.6         # Below this → always HOLD
    HIGH_CONFIDENCE = 0.8        # Above this → bonus +0.1 strength

    SEVERITY_WEIGHTS = {"high": 1.0, "med": 0.7, "low": 0.4}

    BLOCKING_RISK_FLAGS = {"rumor", "low_quality_source"}
    WEAKENING_RISK_FLAGS = {"ambiguous", "already_priced_in"}
    BLOCKING_CONTRADICTION_FLAGS = {"conflicts_with_guidance", "conflicts_with_state"}

    EVENT_TYPE_BIAS = {
        "earnings": 0.0, "guidance": 0.05, "product_launch": 0.05,
        "lawsuit": -0.05, "regulatory": -0.05, "macro": 0.0, "other": 0.0,
    }
```

To modify any threshold, edit the values in `SignalThresholds` and restart the server.

---

## 7. Quick Reference: Decision Tree

```
                    ┌─── confidence < 0.6?  ───→  HOLD
                    │
                    ├─── rumor or low_quality_source?  ───→  HOLD
                    │
                    ├─── conflicts_with_guidance or conflicts_with_state?  ───→  HOLD
                    │
  News Analyzed  ───┤
                    │    adjusted_impact = impact_score + event_bias
                    │
                    ├─── adjusted_impact > +0.3?  ───→  BUY  (strength = f(impact, severity, confidence))
                    │
                    ├─── adjusted_impact < -0.3?  ───→  SELL (strength = f(impact, severity, confidence))
                    │
                    └─── otherwise  ───→  HOLD
```
