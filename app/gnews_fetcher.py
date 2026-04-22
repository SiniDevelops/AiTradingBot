"""
GNews API fetcher module.
Fetches financial news from the GNews API and converts them into
NewsIngestRequest objects for the pipeline.
"""
import os
import uuid
from datetime import datetime
from typing import List, Optional
import requests

from app.models import NewsIngestRequest


# GNews API base URL
GNEWS_BASE_URL = "https://gnews.io/api/v4"

# Default search keywords for Indian market stocks
DEFAULT_SEARCH_QUERIES = [
    "Indian stock market",
    "Reliance Industries",
    "TCS Tata Consultancy",
    "Infosys",
    "HDFC Bank",
    "ICICI Bank",
    "Wipro",
    "Bharti Airtel",
    "ITC Limited",
    "SBI State Bank India",
    "Hindustan Unilever",
    "Nifty sensex",
]


class GNewsFetcher:
    """Fetches financial news articles from GNews API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GNEWS_API_KEY")
        if not self.api_key or self.api_key == "your_gnews_api_key_here":
            raise ValueError(
                "GNews API key not found. Set GNEWS_API_KEY in .env"
            )

    def fetch_top_headlines(
        self,
        category: str = "business",
        lang: str = "en",
        country: str = "in",
        max_articles: int = 10,
    ) -> List[dict]:
        """
        Fetch top business headlines from GNews.

        Args:
            category: News category (business, technology, etc.)
            lang: Language code
            country: Country code (in = India)
            max_articles: Maximum number of articles

        Returns:
            List of raw article dicts from GNews
        """
        url = f"{GNEWS_BASE_URL}/top-headlines"
        params = {
            "category": category,
            "lang": lang,
            "country": country,
            "max": max_articles,
            "apikey": self.api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])
            print(f"[GNews] Fetched {len(articles)} top headlines")
            return articles
        except requests.exceptions.RequestException as e:
            print(f"[GNews] Error fetching top headlines: {e}")
            return []

    def search_news(
        self,
        query: str,
        lang: str = "en",
        country: str = "in",
        max_articles: int = 5,
    ) -> List[dict]:
        """
        Search for news articles matching a query.

        Args:
            query: Search keywords
            lang: Language code
            country: Country code
            max_articles: Maximum articles per query

        Returns:
            List of raw article dicts from GNews
        """
        url = f"{GNEWS_BASE_URL}/search"
        params = {
            "q": query,
            "lang": lang,
            "country": country,
            "max": max_articles,
            "apikey": self.api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])
            print(f"[GNews] Search '{query}': {len(articles)} articles")
            return articles
        except requests.exceptions.RequestException as e:
            print(f"[GNews] Error searching '{query}': {e}")
            return []

    def fetch_market_news(
        self,
        queries: Optional[List[str]] = None,
        max_per_query: int = 3,
    ) -> List[dict]:
        """
        Fetch news across multiple market-related queries.
        Deduplicates by URL.

        Args:
            queries: List of search queries (uses defaults if None)
            max_per_query: Max articles per individual query

        Returns:
            Deduplicated list of articles
        """
        queries = queries or DEFAULT_SEARCH_QUERIES
        seen_urls = set()
        all_articles = []

        # Start with top headlines
        headlines = self.fetch_top_headlines(max_articles=10)
        for article in headlines:
            url = article.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_articles.append(article)

        # Then search each query
        for query in queries:
            articles = self.search_news(query, max_articles=max_per_query)
            for article in articles:
                url = article.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_articles.append(article)

        print(f"[GNews] Total unique articles: {len(all_articles)}")
        return all_articles

    @staticmethod
    def to_ingest_request(article: dict) -> Optional[NewsIngestRequest]:
        """
        Convert a GNews article dict into a NewsIngestRequest.

        GNews article format:
        {
            "title": "...",
            "description": "...",
            "content": "...",
            "url": "...",
            "image": "...",
            "publishedAt": "2024-02-13T09:30:00Z",
            "source": {"name": "Bloomberg", "url": "..."}
        }
        """
        try:
            title = article.get("title", "").strip()
            # Use content first, fall back to description
            content = article.get("content", "") or article.get("description", "")
            if not content:
                content = title  # Last resort

            content = content.strip()
            if not title or not content:
                return None

            source_info = article.get("source", {})
            source_name = source_info.get("name", "GNews") if isinstance(source_info, dict) else "GNews"

            published_str = article.get("publishedAt", "")
            if published_str:
                # GNews uses ISO format
                published_at = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00")
                )
            else:
                published_at = datetime.now()

            # Generate deterministic ID from URL to prevent duplicates
            article_url = article.get("url", "")
            if article_url:
                news_id = f"gnews_{uuid.uuid5(uuid.NAMESPACE_URL, article_url).hex[:12]}"
            else:
                news_id = f"gnews_{uuid.uuid4().hex[:12]}"

            return NewsIngestRequest(
                id=news_id,
                source=source_name,
                published_at=published_at,
                title=title,
                content=content,
            )
        except Exception as e:
            print(f"[GNews] Failed to convert article: {e}")
            return None

    def fetch_and_convert(
        self,
        queries: Optional[List[str]] = None,
        max_per_query: int = 3,
    ) -> List[NewsIngestRequest]:
        """
        Fetch news and convert to NewsIngestRequest objects.
        This is the main entry point for the pipeline.

        Returns:
            List of NewsIngestRequest ready for ingestion
        """
        raw_articles = self.fetch_market_news(queries, max_per_query)

        requests_list = []
        for article in raw_articles:
            req = self.to_ingest_request(article)
            if req:
                requests_list.append(req)

        print(f"[GNews] Converted {len(requests_list)} articles to ingest requests")
        return requests_list


# Module-level convenience
_fetcher: Optional[GNewsFetcher] = None


def get_gnews_fetcher() -> GNewsFetcher:
    """Get or create the global GNews fetcher."""
    global _fetcher
    if _fetcher is None:
        _fetcher = GNewsFetcher()
    return _fetcher
