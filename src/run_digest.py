# src/run_digest.py
"""
Main orchestrator for daily digest generation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import sys

import feedparser
from dotenv import load_dotenv

# Load environment variables from .env file in the project root
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")

from . import feeds
from . import state_store
from . import extract
from . import scoring
from . import gemini_summarize
from . import render
from . import utils

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_feed_items(feed: feeds.Feed, cutoff_dt: datetime) -> List[dict]:
    """
    Fetch items from a single feed that are newer than cutoff_dt.

    Returns list of dicts with: title, url, summary, published_dt, feed_name, feed_weight
    """
    logger.info(f"Fetching feed: {feed.name} ({feed.url})")

    try:
        parsed = feedparser.parse(feed.url)

        if parsed.bozo:
            logger.warning(f"Feed parse warning for {feed.name}: {parsed.get('bozo_exception', 'unknown')}")

        items = []
        for entry in parsed.entries:
            # Extract fields
            title = entry.get("title", "Untitled")
            link = entry.get("link")
            summary = entry.get("summary", entry.get("description", ""))
            published = entry.get("published", entry.get("updated"))

            if not link:
                continue

            # Parse and check date
            published_dt = utils.parse_date(published)
            if not utils.is_recent(published_dt, cutoff_dt):
                continue

            # Normalize URL
            normalized_url = utils.normalize_url(link)

            items.append({
                "title": title,
                "url": normalized_url,
                "summary": summary,
                "published_dt": published_dt,
                "feed_name": feed.name,
                "feed_weight": feed.weight
            })

        logger.info(f"  Found {len(items)} recent items from {feed.name}")
        return items

    except Exception as e:
        logger.error(f"Failed to fetch feed {feed.name}: {e}")
        return []


def build_candidate_pool(
    category: str,
    primary_cutoff: datetime,
    extended_cutoff: datetime,
    max_candidates: int = 10
) -> List[dict]:
    """
    Build a pool of candidate articles for a category.

    Strategy:
    1. Try primary time window (48h) first
    2. If insufficient, expand to 7 days
    3. Pull from curated feeds + Google News RSS fallbacks

    Returns list of candidate dicts.
    """
    logger.info(f"Building candidate pool for category: {category}")

    all_feeds = feeds.all_feeds_for(category)
    candidates = []

    # First pass: primary window (48h)
    for feed in all_feeds:
        items = fetch_feed_items(feed, primary_cutoff)
        candidates.extend(items)

        if len(candidates) >= max_candidates:
            break

    logger.info(f"  Primary window (48h): {len(candidates)} candidates")

    # If insufficient, try extended window (7d)
    if len(candidates) < 3:
        logger.info(f"  Expanding to 7-day window for {category}")
        for feed in all_feeds:
            items = fetch_feed_items(feed, extended_cutoff)
            candidates.extend(items)

            if len(candidates) >= max_candidates:
                break

    # Remove duplicates by URL
    seen_urls = set()
    unique_candidates = []
    for c in candidates:
        if c["url"] not in seen_urls:
            seen_urls.add(c["url"])
            unique_candidates.append(c)

    logger.info(f"  Total unique candidates for {category}: {len(unique_candidates)}")

    return unique_candidates[:max_candidates]


def select_article(
    category: str,
    candidates: List[dict],
    gemini_model
) -> tuple[Optional[dict], List[tuple[str, str]]]:
    """
    Select the best article from candidates for a category.

    Returns:
        (selected_article or None, list of (url, rejection_reason) tuples)

    Process:
    1. Filter out already-seen URLs
    2. Extract article text (with paywall detection)
    3. Score candidates heuristically
    4. Take top 3, ask Gemini to pick best
    5. Summarize selected article
    """
    rejections = []

    # Filter seen URLs
    unseen = []
    for c in candidates:
        if state_store.is_url_seen(c["url"]):
            rejections.append((c["url"], "duplicate"))
        else:
            unseen.append(c)

    if not unseen:
        logger.warning(f"No unseen candidates for {category}")
        return None, rejections

    # Extract article text for each candidate
    extracted = []
    for c in unseen:
        text, status = extract.extract_article_text(c["url"], c.get("summary"))

        if status == "paywall":
            rejections.append((c["url"], "paywall"))
            continue
        elif status in ("fetch_failed", "extraction_failed", "too_short"):
            rejections.append((c["url"], f"extraction failed ({status})"))
            continue
        elif text is None:
            rejections.append((c["url"], "no text available"))
            continue

        c["extracted_text"] = text
        c["extraction_status"] = status
        extracted.append(c)

    if not extracted:
        logger.warning(f"No extractable candidates for {category}")
        return None, rejections

    # Score and rank
    top_candidates = scoring.rank_candidates(extracted, category, top_n=3)

    if not top_candidates:
        logger.warning(f"No ranked candidates for {category}")
        return None, rejections

    # If only one candidate, use it
    if len(top_candidates) == 1:
        selected = top_candidates[0]
    else:
        # Ask Gemini to pick the best among top candidates
        selected = _gemini_select_best(top_candidates, category, gemini_model)

    # Add non-selected to rejections
    for c in top_candidates:
        if c["url"] != selected["url"]:
            rejections.append((c["url"], "not selected (lower relevance)"))

    # Summarize selected article
    logger.info(f"Selected for {category}: {selected['title']}")
    bullets = gemini_summarize.summarize_article(selected["extracted_text"], gemini_model)

    result = {
        "title": selected["title"],
        "url": selected["url"],
        "bullets": bullets
    }

    return result, rejections


def _gemini_select_best(candidates: List[dict], category: str, gemini_model) -> dict:
    """
    Use Gemini to pick the best article among top candidates.

    Fallback to highest-scored if Gemini fails.
    """
    # Build prompt with candidate summaries
    candidate_texts = []
    for i, c in enumerate(candidates, 1):
        snippet = c["extracted_text"][:500]
        candidate_texts.append(f"Candidate {i}: {c['title']}\n{snippet}\n")

    prompt = f"""You are selecting the single most relevant and newsworthy article for the "{category}" category in a daily digest.

Here are the top candidates:

{"".join(candidate_texts)}

Which candidate is most relevant and interesting for readers interested in {category}?
Answer with just the number (1, 2, or 3)."""

    try:
        response = gemini_model.generate_content(prompt)
        choice_text = response.text.strip()

        # Parse choice
        import re
        match = re.search(r'\b([123])\b', choice_text)
        if match:
            choice_idx = int(match.group(1)) - 1
            if 0 <= choice_idx < len(candidates):
                logger.info(f"Gemini selected candidate {choice_idx + 1}")
                return candidates[choice_idx]

        logger.warning(f"Could not parse Gemini choice: '{choice_text}', using top-scored")
    except Exception as e:
        logger.error(f"Gemini selection failed: {e}, using top-scored")

    # Fallback to highest score
    return candidates[0]


def run_digest() -> None:
    """Main entry point for digest generation."""
    logger.info("Starting daily digest generation")

    # Initialize state store
    state_store.init_db()

    # Initialize Gemini
    try:
        gemini_model = gemini_summarize.init_gemini()
    except Exception as e:
        logger.error(f"Failed to initialize Gemini: {e}")
        sys.exit(1)

    # Compute time windows
    now = datetime.now(timezone.utc)
    primary_cutoff = now - timedelta(hours=48)
    extended_cutoff = now - timedelta(days=7)

    # Today's date for filenames
    today = now.date()

    # Track sources used and rejections
    all_rejections = []
    source_pools = {}
    selected_articles = {}

    # Process each category
    for category in feeds.CATEGORIES:
        logger.info(f"\n{'='*60}\nProcessing category: {category}\n{'='*60}")

        # Build candidate pool
        candidates = build_candidate_pool(category, primary_cutoff, extended_cutoff)

        # Track sources
        source_names = list(set(c["feed_name"] for c in candidates))
        source_pools[category] = source_names

        if not candidates:
            logger.warning(f"No candidates found for {category}")
            selected_articles[category] = None
            continue

        # Select best article
        article, rejections = select_article(category, candidates, gemini_model)
        selected_articles[category] = article
        all_rejections.extend(rejections)

        # Mark selected URL as seen
        if article:
            state_store.mark_url_seen(article["url"])

    # Render digest
    digest_content = render.render_digest(
        digest_date=today,
        articles=selected_articles,
        source_pools=source_pools,
        rejections=all_rejections
    )

    # Save to digests/YYYY-MM-DD.md
    digest_dir = Path(__file__).parent.parent / "digests"
    digest_dir.mkdir(exist_ok=True)
    digest_file = digest_dir / f"{today}.md"
    digest_file.write_text(digest_content, encoding="utf-8")
    logger.info(f"Saved digest to {digest_file}")

    # Update README
    readme_path = Path(__file__).parent.parent / "README.md"
    render.update_readme(readme_path, digest_content)
    logger.info(f"Updated README.md")

    logger.info("Digest generation complete!")


if __name__ == "__main__":
    run_digest()
