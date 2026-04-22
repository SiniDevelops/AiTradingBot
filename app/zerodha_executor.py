"""
Zerodha Kite Connect order execution module.
Handles authentication and order placement for BUY/SELL signals.
"""
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from app.models import SignalResult, SignalType


class ZerodhaExecutor:
    """
    Executes trading orders via Zerodha Kite Connect API.

    Handles:
    - Authentication (request_token → access_token)
    - Order placement (BUY/SELL market orders)
    - Graceful fallback to logging when auth fails
    - Order tracking in database
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        request_token: Optional[str] = None,
        trading_mode: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("KITE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("KITE_API_SECRET", "")
        self.request_token = request_token or os.getenv("KITE_REQUEST_TOKEN", "")
        self.trading_mode = trading_mode or os.getenv("TRADING_MODE", "paper")
        self.kite = None
        self.authenticated = False
        self.access_token = None

        # Default order settings
        self.default_quantity = int(os.getenv("DEFAULT_ORDER_QUANTITY", "1"))
        self.max_capital_per_trade = float(os.getenv("MAX_CAPITAL_PER_TRADE", "10000"))

    def authenticate(self) -> bool:
        """
        Authenticate with Kite Connect.
        Exchanges request_token for access_token.

        Returns:
            True if authentication succeeded, False otherwise
        """
        if not self.api_key or self.api_key == "your_kite_api_key_here":
            print("[Zerodha] No API key configured. Running in log-only mode.")
            return False

        if not self.api_secret or self.api_secret == "your_kite_api_secret_here":
            print("[Zerodha] No API secret configured. Running in log-only mode.")
            return False

        if not self.request_token or self.request_token == "your_kite_request_token_here":
            print("[Zerodha] No request token configured. Running in log-only mode.")
            return False

        try:
            from kiteconnect import KiteConnect

            self.kite = KiteConnect(api_key=self.api_key)

            # Exchange request_token for access_token
            data = self.kite.generate_session(
                self.request_token, api_secret=self.api_secret
            )
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            self.authenticated = True

            print(f"[Zerodha] Authenticated successfully. "
                  f"User: {data.get('user_name', 'unknown')}")
            return True

        except Exception as e:
            print(f"[Zerodha] Authentication failed: {e}")
            print("[Zerodha] Falling back to log-only mode.")
            self.authenticated = False
            return False

    def execute_signal(
        self,
        signal_result: SignalResult,
        quantity: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a trading signal.

        Args:
            signal_result: The signal to execute
            quantity: Number of shares (defaults to self.default_quantity)

        Returns:
            Dict with execution result:
            {
                "ticker": str,
                "signal": str,
                "action_taken": str,
                "order_id": str or None,
                "quantity": int,
                "status": "executed" | "logged" | "skipped",
                "message": str,
                "timestamp": str
            }
        """
        qty = quantity or self.default_quantity
        ticker = signal_result.ticker
        signal = signal_result.signal

        result = {
            "ticker": ticker,
            "signal": signal.value,
            "strength": signal_result.strength,
            "action_taken": "none",
            "order_id": None,
            "quantity": qty,
            "status": "skipped",
            "message": "",
            "timestamp": datetime.now().isoformat(),
        }

        # HOLD signals are always skipped
        if signal == SignalType.HOLD:
            result["action_taken"] = "HOLD"
            result["status"] = "skipped"
            result["message"] = (
                f"HOLD signal for {ticker} — no action taken. "
                f"Reasons: {'; '.join(signal_result.reasons)}"
            )
            print(f"[Zerodha] [=] HOLD {ticker} (strength={signal_result.strength:.2f})")
            return result

        # Determine transaction type
        if signal == SignalType.BUY:
            transaction_type = "BUY"
        elif signal == SignalType.SELL:
            transaction_type = "SELL"
        else:
            result["message"] = f"Unknown signal type: {signal}"
            return result

        result["action_taken"] = transaction_type

        # Paper trading mode — just log
        if self.trading_mode == "paper":
            result["status"] = "logged"
            result["message"] = (
                f"[PAPER] {transaction_type} {qty}x {ticker} "
                f"(strength={signal_result.strength:.2f}, "
                f"impact={signal_result.impact_score:+.2f}). "
                f"Reasons: {'; '.join(signal_result.reasons)}"
            )
            emoji = "[+]" if transaction_type == "BUY" else "[-]"
            print(f"[Zerodha] {emoji} PAPER {transaction_type} {qty}x {ticker}")
            return result

        # Live mode — needs authentication
        if not self.authenticated or not self.kite:
            result["status"] = "logged"
            result["message"] = (
                f"[NOT AUTHENTICATED] Would {transaction_type} {qty}x {ticker}. "
                f"Kite auth required for live execution."
            )
            print(f"[Zerodha] [!] NOT AUTHENTICATED - logged {transaction_type} {ticker}")
            return result

        # Live execution via Kite Connect
        try:
            from kiteconnect import KiteConnect

            kite_transaction = (
                self.kite.TRANSACTION_TYPE_BUY
                if transaction_type == "BUY"
                else self.kite.TRANSACTION_TYPE_SELL
            )

            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                tradingsymbol=ticker,
                exchange=self.kite.EXCHANGE_NSE,
                transaction_type=kite_transaction,
                quantity=qty,
                order_type=self.kite.ORDER_TYPE_MARKET,
                product=self.kite.PRODUCT_MIS,  # Intraday
                validity=self.kite.VALIDITY_DAY,
            )

            result["order_id"] = str(order_id)
            result["status"] = "executed"
            result["message"] = (
                f"[LIVE] {transaction_type} {qty}x {ticker} — "
                f"Order ID: {order_id}"
            )

            emoji = "[+]" if transaction_type == "BUY" else "[-]"
            print(
                f"[Zerodha] {emoji} LIVE {transaction_type} {qty}x {ticker} "
                f"- Order ID: {order_id}"
            )
            return result

        except Exception as e:
            result["status"] = "failed"
            result["message"] = (
                f"[FAILED] {transaction_type} {qty}x {ticker} — Error: {str(e)}"
            )
            print(f"[Zerodha] [X] FAILED {transaction_type} {ticker}: {e}")
            return result

    def get_positions(self) -> Dict[str, Any]:
        """Get current positions from Kite."""
        if not self.authenticated or not self.kite:
            return {"status": "not_authenticated", "positions": []}

        try:
            positions = self.kite.positions()
            return {"status": "ok", "positions": positions}
        except Exception as e:
            return {"status": "error", "message": str(e), "positions": []}

    def get_holdings(self) -> Dict[str, Any]:
        """Get current holdings from Kite."""
        if not self.authenticated or not self.kite:
            return {"status": "not_authenticated", "holdings": []}

        try:
            holdings = self.kite.holdings()
            return {"status": "ok", "holdings": holdings}
        except Exception as e:
            return {"status": "error", "message": str(e), "holdings": []}


# Module-level convenience
_executor: Optional[ZerodhaExecutor] = None


def get_zerodha_executor() -> ZerodhaExecutor:
    """Get or create the global Zerodha executor."""
    global _executor
    if _executor is None:
        _executor = ZerodhaExecutor()
    return _executor


def init_zerodha() -> ZerodhaExecutor:
    """Initialize and authenticate Zerodha executor."""
    executor = get_zerodha_executor()
    executor.authenticate()
    return executor
