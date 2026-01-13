# src/scoring.py
"""
Heuristic scoring for article relevance by category.
"""
from __future__ import annotations

import re
from typing import Dict, List
from urllib.parse import urlparse


# Category-specific keywords for relevance scoring
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "llms": [
        "llm", "large language model", "gpt", "chatgpt", "claude", "gemini",
        "foundation model", "transformer", "anthropic", "openai",
        "prompt engineering", "context window", "tokens", "fine-tuning",
        "rlhf", "alignment", "constitutional ai", "llama"
    ],
    "ai": [
        "artificial intelligence", "machine learning", "deep learning",
        "neural network", "ai model", "inference", "training",
        "computer vision", "nlp", "natural language",
        "mlops", "ai safety", "ai policy", "ai regulation",
        "ai startup", "ai chip", "gpu", "datacenter", "nvidia",
        "ai deployment", "open source ai"
    ],
    "markets": [
        "stock", "market", "trading", "s&p", "nasdaq", "dow",
        "earnings", "volatility", "inflation", "fed", "federal reserve",
        "interest rate", "bond", "yield", "equity", "commodity",
        "central bank", "monetary policy", "risk", "portfolio",
        "index", "rally", "sell-off", "valuation", "macro"
    ],
}


# Quality publishers (domain-based boost)
QUALITY_PUBLISHERS = {
    # Tech/AI
    "theverge.com": 1.2,
    "wired.com": 1.2,
    "arstechnica.com": 1.2,
    "techcrunch.com": 1.1,
    "technologyreview.com": 1.3,
    "blog.cloudflare.com": 1.2,
    "engineering.fb.com": 1.2,
    "openai.com": 1.3,
    "anthropic.com": 1.3,
    # Markets
    "reuters.com": 1.2,
    "bloomberg.com": 1.2,
    "ft.com": 1.3,
    "wsj.com": 1.2,
    "marketwatch.com": 1.1,
    "investing.com": 1.0,
}


def score_article(
    title: str,
    summary: str,
    url: str,
    category: str,
    feed_weight: float = 1.0
) -> float:
    """
    Compute a heuristic relevance score for an article.

    Factors:
    - Keyword matches in title/summary (by category)
    - Publisher quality boost
    - Feed weight
    - arXiv penalty

    Returns a float score (higher = more relevant).
    """
    score = 0.0

    # Combine title and summary for keyword matching
    text = (title + " " + summary).lower()

    # Keyword matching
    keywords = CATEGORY_KEYWORDS.get(category, [])
    for kw in keywords:
        # Count occurrences (with diminishing returns)
        count = text.count(kw.lower())
        if count > 0:
            score += min(count, 3) * 0.5  # Cap contribution per keyword

    # Publisher boost
    domain = urlparse(url).netloc.lower()
    # Remove www. prefix
    if domain.startswith("www."):
        domain = domain[4:]

    publisher_boost = QUALITY_PUBLISHERS.get(domain, 1.0)
    score *= publisher_boost

    # Feed weight
    score *= feed_weight

    # arXiv penalty (strongly discourage)
    if "arxiv.org" in domain:
        score *= 0.2  # Heavy penalty

    return score


def rank_candidates(candidates: List[dict], category: str, top_n: int = 3) -> List[dict]:
    """
    Rank candidates by score and return top N.

    Each candidate dict should have:
    - title: str
    - summary: str
    - url: str
    - feed_weight: float

    Returns sorted list (highest score first), limited to top_n.
    """
    for candidate in candidates:
        candidate["score"] = score_article(
            title=candidate.get("title", ""),
            summary=candidate.get("summary", ""),
            url=candidate["url"],
            category=category,
            feed_weight=candidate.get("feed_weight", 1.0)
        )

    # Sort by score descending
    ranked = sorted(candidates, key=lambda c: c["score"], reverse=True)

    return ranked[:top_n]
