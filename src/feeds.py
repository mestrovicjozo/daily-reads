# src/feeds.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Feed:
    """A single RSS/Atom feed source."""
    name: str
    url: str
    category: str  # "llms" | "ai" | "markets"
    weight: float = 1.0  # optional heuristic boost for candidates from this feed


CATEGORIES = ("llms", "ai", "markets")

# --- Curated direct RSS feeds (primary signal, low noise) ---
# Note: Feeds occasionally change. Your pipeline should tolerate failures and keep going.
FEEDS: List[Feed] = [
    # Tech / AI-adjacent (often covers LLM product moves + industry)
    Feed("The Verge", "https://www.theverge.com/rss/index.xml", "ai", 1.0),
    Feed("Wired", "https://www.wired.com/feed/rss", "ai", 1.0),
    Feed("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "ai", 1.0),
    Feed("TechCrunch", "https://techcrunch.com/feed/", "ai", 1.0),
    Feed("MIT Technology Review", "https://www.technologyreview.com/feed/", "ai", 1.1),

    # Engineering / infrastructure (good for “real AI in production”)
    Feed("Cloudflare Blog", "https://blog.cloudflare.com/rss/", "ai", 1.0),
    Feed("Meta Engineering", "https://engineering.fb.com/feed/", "ai", 1.0),

    # Markets (direct finance RSS is hit-or-miss; keep a couple + rely on Google News RSS)
    # If these are flaky, your code should simply skip them and use fallback.
    Feed("MarketWatch: Top Stories", "https://feeds.marketwatch.com/marketwatch/topstories/", "markets", 1.0),
    Feed("Investing.com: News", "https://www.investing.com/rss/news.rss", "markets", 0.9),
]

# --- Google News RSS fallback (secondary, broad coverage) ---
# You’ll use these when curated feeds don’t produce enough candidates in the time window.
# hl=en & gl=US keep results in English; you can tweak regions later if needed.
GOOGLE_NEWS_RSS_BASE = "https://news.google.com/rss/search"

CATEGORY_QUERIES: Dict[str, List[str]] = {
    "llms": [
        '("large language model" OR LLM OR "foundation model") (OpenAI OR Anthropic OR Google OR Meta OR Microsoft)',
        '("LLM" OR "large language model") (release OR update OR launch OR safety OR evals)',
        '("ChatGPT" OR "Claude" OR "Gemini" OR "Llama") (model OR update OR API)',
    ],
    "ai": [
        '(AI OR "artificial intelligence") (product OR policy OR regulation OR chips OR datacenter OR inference)',
        '(AI) (startup OR funding OR acquisition OR "open source")',
        '("machine learning") (engineering OR deployment OR "MLOps" OR inference)',
    ],
    "markets": [
        '("financial markets" OR stocks OR bonds OR inflation OR rates OR "central bank") (outlook OR volatility)',
        '(S&P OR Nasdaq OR Dow OR "earnings" OR "macro data") (today OR week OR outlook)',
        '("market rally" OR "sell-off" OR "risk-on" OR "risk-off") (stocks OR global)',
    ],
}

def google_news_rss_url(query: str, *, hl: str = "en", gl: str = "US", ceid: str = "US:en") -> str:
    """
    Build a Google News RSS URL for a query.
    Example output:
      https://news.google.com/rss/search?q=...&hl=en&gl=US&ceid=US:en
    """
    q = quote_plus(query)
    return f"{GOOGLE_NEWS_RSS_BASE}?q={q}&hl={hl}&gl={gl}&ceid={ceid}"

def fallback_google_news_feeds_for(category: str) -> List[Feed]:
    """Return fallback Google News RSS 'feeds' for a given category."""
    if category not in CATEGORY_QUERIES:
        raise ValueError(f"Unknown category: {category}")
    feeds: List[Feed] = []
    for i, q in enumerate(CATEGORY_QUERIES[category], start=1):
        feeds.append(
            Feed(
                name=f"Google News RSS ({category.upper()} #{i})",
                url=google_news_rss_url(q),
                category=category,
                weight=0.85,  # slightly lower than curated feeds
            )
        )
    return feeds

def all_feeds_for(category: str) -> List[Feed]:
    """Curated feeds first, then Google News RSS fallbacks."""
    curated = [f for f in FEEDS if f.category == category]
    return curated + fallback_google_news_feeds_for(category)
