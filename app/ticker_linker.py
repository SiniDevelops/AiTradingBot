"""
Ticker linking and entity recognition module.
"""
import re
from typing import List, Set

# Simple ticker alias dictionary
TICKER_ALIASES = {
    "Apple": ["AAPL", "apple", "apple inc", "apple computer"],
    "Microsoft": ["MSFT", "microsoft", "microsoft corp"],
    "Tesla": ["TSLA", "tesla", "tesla inc"],
    "Meta": ["META", "meta", "facebook", "fb"],
    "Amazon": ["AMZN", "amazon", "aws"],
    "Google": ["GOOGL", "GOOG", "google", "alphabet"],
    "NVIDIA": ["NVDA", "nvidia"],
    "Berkshire": ["BRK", "BRK.A", "BRK.B", "berkshire hathaway"],
}

# Build reverse mapping (mention -> ticker list)
MENTION_TO_TICKERS = {}
for entity, tickers in TICKER_ALIASES.items():
    for mention in tickers:
        if mention not in MENTION_TO_TICKERS:
            MENTION_TO_TICKERS[mention.lower()] = []
        MENTION_TO_TICKERS[mention.lower()].extend([t for t in tickers if len(t) <= 5])


def link_tickers(text: str, title: str) -> List[str]:
    """
    Extract ticker mentions from text using simple pattern matching and alias map.
    
    Returns:
        List of unique ticker symbols found.
    """
    found_tickers: Set[str] = set()
    
    # Combine title and content for searching
    combined = f"{title} {text}".lower()
    
    # Rule 1: Direct ticker patterns (e.g., $AAPL, AAPL:, @AAPL)
    ticker_patterns = [
        r'\$([A-Z]{1,5})\b',      # $AAPL
        r'\b([A-Z]{1,5}):\b',     # AAPL:
        r'@([A-Z]{1,5})\b',       # @AAPL
        r'\(([A-Z]{1,5})\)',      # (AAPL)
    ]
    
    for pattern in ticker_patterns:
        matches = re.finditer(pattern, combined)
        for match in matches:
            ticker = match.group(1).upper()
            found_tickers.add(ticker)
    
    # Rule 2: Alias-based matching
    for mention, tickers in MENTION_TO_TICKERS.items():
        # Whole-word matching to avoid false positives
        pattern = r'\b' + re.escape(mention) + r'\b'
        if re.search(pattern, combined):
            found_tickers.update(tickers)
    
    # Filter to valid ticker formats
    valid_tickers = [t for t in found_tickers if re.match(r'^[A-Z]{1,5}$', t)]
    
    return sorted(list(set(valid_tickers)))


def are_tickers_related(ticker1: str, ticker2: str) -> bool:
    """Check if two tickers are related (same entity)."""
    # Build entity map for grouping
    for entity, tickers in TICKER_ALIASES.items():
        valid_tickers_for_entity = [t for t in tickers if len(t) <= 5]
        if ticker1 in valid_tickers_for_entity and ticker2 in valid_tickers_for_entity:
            return True
    return False
