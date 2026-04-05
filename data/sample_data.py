"""
Sample mock data for testing the trading bot.
"""
import json
from datetime import datetime

# Sample tickers
SAMPLE_TICKERS = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"]

# Sample mock news articles
SAMPLE_NEWS = [
    {
        "id": "sample_001",
        "source": "Bloomberg",
        "published_at": "2024-02-13T09:30:00Z",
        "title": "Apple Beats Q1 2024 Earnings, Raises Guidance",
        "content": """
        Apple Inc. reported Q1 2024 earnings that exceeded analyst expectations,
        with revenue of $84.3 billion, up 5% year-over-year. EPS came in at $2.18,
        beating estimates of $2.10. CEO Tim Cook stated: "We're optimistic about
        the iPhone 15 Pro demand and our services business continues to grow."
        The company raised full-year revenue guidance to $380-390 billion.
        Stock symbol: $AAPL. Analysts are raising price targets on the strong results.
        """
    },
    {
        "id": "sample_002",
        "source": "Reuters",
        "published_at": "2024-02-13T14:00:00Z",
        "title": "Google Faces Regulatory Scrutiny Over AI Search",
        "content": """
        Alphabet Inc. (ticker: GOOGL) is facing renewed regulatory scrutiny from
        the SEC regarding its AI-powered search features. Regulators are concerned
        about potential antitrust issues and user privacy implications. An investigation
        has been announced by the Department of Justice. Google stated it is cooperating
        fully with regulators. This could impact Google's ability to roll out AI features.
        Stock ticker: GOOGL.
        """
    },
    {
        "id": "sample_003",
        "source": "TechCrunch",
        "published_at": "2024-02-13T16:45:00Z",
        "title": "Microsoft Announces $10B AI Partnership with OpenAI",
        "content": """
        Microsoft Corporation (MSFT) announced today a landmark $10 billion investment
        in OpenAI as part of an expanded partnership. The deal will accelerate AI
        innovation and product integration across Microsoft's cloud and enterprise
        offerings. This positions Microsoft as a key player in enterprise AI.
        Analysts are bullish on the strategic move. MSFT stock rose 2.3% on the news.
        The partnership will focus on Azure cloud infrastructure and AI model development.
        """
    }
]

# Expected analysis outputs for mock data
EXPECTED_ANALYSES = {
    "sample_001": {
        "ticker": "AAPL",
        "event_type": "earnings",
        "is_new_information": True,
        "impact_score": 0.5,
        "horizon": "swing",
        "severity": "med",
        "confidence": 0.85,
    },
    "sample_002": {
        "ticker": "GOOGL",
        "event_type": "regulatory",
        "is_new_information": True,
        "impact_score": -0.6,
        "horizon": "long",
        "severity": "high",
        "confidence": 0.8,
    },
    "sample_003": {
        "ticker": "MSFT",
        "event_type": "macro",
        "is_new_information": True,
        "impact_score": 0.7,
        "horizon": "long",
        "severity": "high",
        "confidence": 0.75,
    }
}


def get_sample_news_items():
    """Return sample news items as list of dicts."""
    return SAMPLE_NEWS


def get_expected_analysis(news_id: str):
    """Get expected analysis for a sample news item."""
    return EXPECTED_ANALYSES.get(news_id, {})


if __name__ == "__main__":
    print("Sample News Data:")
    print(json.dumps(SAMPLE_NEWS, indent=2))
    print("\nExpected Analyses:")
    print(json.dumps(EXPECTED_ANALYSES, indent=2))
