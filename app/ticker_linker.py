"""
Ticker linking and entity recognition module.
"""
import re
from typing import List, Set

# Simple ticker alias dictionary
# US Market Tickers
TICKER_ALIASES = {
    "Apple": ["AAPL", "apple", "apple inc", "apple computer"],
    "Microsoft": ["MSFT", "microsoft", "microsoft corp"],
    "Tesla": ["TSLA", "tesla", "tesla inc"],
    "Meta": ["META", "meta", "facebook", "fb"],
    "Amazon": ["AMZN", "amazon", "aws"],
    "Google": ["GOOGL", "GOOG", "google", "alphabet"],
    "NVIDIA": ["NVDA", "nvidia"],
    "Berkshire": ["BRK", "BRK.A", "BRK.B", "berkshire hathaway"],
    # Indian Market Tickers (NSE)
    "Reliance": ["RELIANCE", "reliance", "reliance industries", "ril", "mukesh ambani"],
    "TCS": ["TCS", "tcs", "tata consultancy", "tata consultancy services"],
    "Infosys": ["INFY", "infosys", "infosys ltd", "infosys limited"],
    "HDFC Bank": ["HDFCBANK", "hdfc bank", "hdfc", "housing development finance"],
    "ICICI Bank": ["ICICIBANK", "icici bank", "icici"],
    "Wipro": ["WIPRO", "wipro", "wipro ltd", "wipro limited"],
    "Bharti Airtel": ["BHARTIARTL", "airtel", "bharti airtel", "bharti"],
    "ITC": ["ITC", "itc", "itc limited"],
    "SBI": ["SBIN", "sbi", "state bank", "state bank of india"],
    "HUL": ["HINDUNILVR", "hul", "hindustan unilever", "hindustan unilever limited"],
    "Bajaj Finance": ["BAJFINANCE", "bajaj finance", "bajaj"],
    "Kotak Bank": ["KOTAKBANK", "kotak", "kotak mahindra", "kotak mahindra bank"],
    "LT": ["LT", "larsen", "larsen & toubro", "larsen and toubro", "l&t"],
    "Maruti": ["MARUTI", "maruti", "maruti suzuki", "maruti suzuki india"],
    "Asian Paints": ["ASIANPAINT", "asian paints", "asian paint"],
    "Titan": ["TITAN", "titan", "titan company", "titan industries"],
    "Sun Pharma": ["SUNPHARMA", "sun pharma", "sun pharmaceutical", "sun pharma ltd"],
    "Tata Motors": ["TATAMOTORS", "tata motors", "tata motor"],
    "Tata Steel": ["TATASTEEL", "tata steel"],
    "Power Grid": ["POWERGRID", "power grid", "power grid corporation"],
    "NTPC": ["NTPC", "ntpc", "ntpc limited"],
    "Adani Enterprises": ["ADANIENT", "adani", "adani enterprises", "adani group"],
    "Adani Ports": ["ADANIPORTS", "adani ports", "adani port"],
    "HCL Tech": ["HCLTECH", "hcl", "hcl tech", "hcl technologies"],
    "Tech Mahindra": ["TECHM", "tech mahindra", "tech m"],
    "Axis Bank": ["AXISBANK", "axis bank", "axis"],
    "IndusInd Bank": ["INDUSINDBK", "indusind", "indusind bank"],
    "Nifty": ["NIFTY", "nifty", "nifty 50", "nifty50"],
    "Sensex": ["SENSEX", "sensex", "bse sensex"],
}

# Build reverse mapping (mention -> ticker list)
MENTION_TO_TICKERS = {}
for entity, tickers in TICKER_ALIASES.items():
    for mention in tickers:
        if mention not in MENTION_TO_TICKERS:
            MENTION_TO_TICKERS[mention.lower()] = []
        MENTION_TO_TICKERS[mention.lower()].extend([t for t in tickers if re.match(r'^[A-Z]{1,12}$', t)])


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
    # Filter to valid ticker formats (up to 12 chars for NSE symbols)
    valid_tickers = [t for t in found_tickers if re.match(r'^[A-Z]{1,12}$', t)]
    
    return sorted(list(set(valid_tickers)))


def are_tickers_related(ticker1: str, ticker2: str) -> bool:
    """Check if two tickers are related (same entity)."""
    # Build entity map for grouping
    for entity, tickers in TICKER_ALIASES.items():
        valid_tickers_for_entity = [t for t in tickers if re.match(r'^[A-Z]{1,12}$', t)]
        if ticker1 in valid_tickers_for_entity and ticker2 in valid_tickers_for_entity:
            return True
    return False
