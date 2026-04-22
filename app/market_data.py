"""
Market data module using yfinance.
Fetches real-time stock prices, historical data, and computes
technical indicators (RSI, SMA crossover, price change) for
signal enrichment.
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import yfinance as yf


# NSE ticker suffix for yfinance
NSE_SUFFIX = ".NS"

# Mapping from our internal tickers to yfinance symbols
# US tickers work directly, NSE tickers need ".NS" suffix
US_TICKERS = {"AAPL", "MSFT", "TSLA", "META", "AMZN", "GOOGL", "GOOG", "NVDA", "BRK"}
INDEX_TICKERS = {"NIFTY", "SENSEX"}  # Skip these - not tradeable


def to_yfinance_symbol(ticker: str) -> str:
    """Convert internal ticker to yfinance symbol."""
    if ticker in US_TICKERS:
        return ticker
    if ticker in INDEX_TICKERS:
        return ""  # Not fetchable
    # Assume NSE for everything else
    return f"{ticker}{NSE_SUFFIX}"


class MarketContext:
    """Container for market data context about a stock."""

    def __init__(
        self,
        ticker: str,
        current_price: float = 0.0,
        prev_close: float = 0.0,
        day_change_pct: float = 0.0,
        rsi_14: float = 50.0,
        sma_9: float = 0.0,
        sma_21: float = 0.0,
        sma_signal: str = "neutral",  # "bullish", "bearish", "neutral"
        volume_ratio: float = 1.0,  # current vol / avg vol
        week_52_high: float = 0.0,
        week_52_low: float = 0.0,
        near_52w_high: bool = False,  # within 5% of 52w high
        near_52w_low: bool = False,   # within 5% of 52w low
        data_available: bool = False,
        error: str = "",
    ):
        self.ticker = ticker
        self.current_price = current_price
        self.prev_close = prev_close
        self.day_change_pct = day_change_pct
        self.rsi_14 = rsi_14
        self.sma_9 = sma_9
        self.sma_21 = sma_21
        self.sma_signal = sma_signal
        self.volume_ratio = volume_ratio
        self.week_52_high = week_52_high
        self.week_52_low = week_52_low
        self.near_52w_high = near_52w_high
        self.near_52w_low = near_52w_low
        self.data_available = data_available
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "current_price": self.current_price,
            "prev_close": self.prev_close,
            "day_change_pct": round(self.day_change_pct, 2),
            "rsi_14": round(self.rsi_14, 2),
            "sma_9": round(self.sma_9, 2),
            "sma_21": round(self.sma_21, 2),
            "sma_signal": self.sma_signal,
            "volume_ratio": round(self.volume_ratio, 2),
            "week_52_high": self.week_52_high,
            "week_52_low": self.week_52_low,
            "near_52w_high": self.near_52w_high,
            "near_52w_low": self.near_52w_low,
            "data_available": self.data_available,
        }

    def summary(self) -> str:
        """One-line summary for logging."""
        if not self.data_available:
            return f"{self.ticker}: No market data"
        return (
            f"{self.ticker}: Rs.{self.current_price:.2f} "
            f"({self.day_change_pct:+.2f}%) "
            f"RSI={self.rsi_14:.0f} "
            f"SMA={self.sma_signal}"
        )


def compute_rsi(prices: List[float], period: int = 14) -> float:
    """Compute RSI from a list of closing prices."""
    if len(prices) < period + 1:
        return 50.0  # default neutral

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    # Use exponential moving average for RSI
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def fetch_market_context(ticker: str) -> MarketContext:
    """
    Fetch current market data and compute technical indicators for a ticker.

    Uses yfinance to get:
    - Current price & day change
    - 14-day RSI
    - 9-day and 21-day SMA (crossover signal)
    - Volume ratio (today vs 20-day avg)
    - 52-week high/low proximity

    Returns:
        MarketContext with all computed data
    """
    import math

    yf_symbol = to_yfinance_symbol(ticker)
    if not yf_symbol:
        return MarketContext(ticker=ticker, error="Index ticker, not fetchable")

    try:
        stock = yf.Ticker(yf_symbol)

        # Fetch 3 months of daily history (enough for RSI-14 and SMAs)
        hist = stock.history(period="3mo")

        if hist.empty:
            return MarketContext(
                ticker=ticker,
                error=f"No data returned for {yf_symbol}",
            )

        # Drop rows with NaN close prices (weekends, holidays, incomplete data)
        hist = hist.dropna(subset=["Close"])

        if len(hist) < 2:
            return MarketContext(
                ticker=ticker,
                error="Insufficient price history after cleaning",
            )

        closes = hist["Close"].tolist()
        volumes = hist["Volume"].tolist()

        # Filter out any remaining NaN/inf values
        closes = [c for c in closes if not (math.isnan(c) or math.isinf(c))]
        volumes = [v if not (math.isnan(v) or math.isinf(v)) else 0 for v in volumes]

        if len(closes) < 2:
            return MarketContext(
                ticker=ticker,
                error="Insufficient valid price data",
            )

        current_price = closes[-1]
        prev_close = closes[-2]
        day_change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0

        # RSI-14
        rsi_14 = compute_rsi(closes, period=14)

        # SMA 9 & 21
        sma_9 = sum(closes[-9:]) / min(9, len(closes)) if len(closes) >= 9 else current_price
        sma_21 = sum(closes[-21:]) / min(21, len(closes)) if len(closes) >= 21 else current_price

        # SMA crossover signal
        if sma_9 > sma_21 * 1.005:  # 0.5% above
            sma_signal = "bullish"
        elif sma_9 < sma_21 * 0.995:  # 0.5% below
            sma_signal = "bearish"
        else:
            sma_signal = "neutral"

        # Volume ratio
        valid_volumes = [v for v in volumes[-20:] if v > 0]
        avg_volume = sum(valid_volumes) / len(valid_volumes) if valid_volumes else 1
        current_volume = volumes[-1] if volumes else 0
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # 52-week high/low
        year_closes = closes[-252:] if len(closes) >= 252 else closes
        week_52_high = max(year_closes)
        week_52_low = min(year_closes)
        near_52w_high = current_price >= week_52_high * 0.95
        near_52w_low = current_price <= week_52_low * 1.05

        ctx = MarketContext(
            ticker=ticker,
            current_price=current_price,
            prev_close=prev_close,
            day_change_pct=day_change_pct,
            rsi_14=rsi_14,
            sma_9=sma_9,
            sma_21=sma_21,
            sma_signal=sma_signal,
            volume_ratio=volume_ratio,
            week_52_high=week_52_high,
            week_52_low=week_52_low,
            near_52w_high=near_52w_high,
            near_52w_low=near_52w_low,
            data_available=True,
        )

        print(f"[Market] {ctx.summary()}")
        return ctx

    except Exception as e:
        print(f"[Market] Error fetching {yf_symbol}: {e}")
        return MarketContext(ticker=ticker, error=str(e))


def fetch_multiple(tickers: List[str]) -> Dict[str, MarketContext]:
    """Fetch market context for multiple tickers."""
    results = {}
    for ticker in tickers:
        results[ticker] = fetch_market_context(ticker)
    return results
