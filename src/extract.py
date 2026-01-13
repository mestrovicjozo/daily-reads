# src/extract.py
"""
Article text extraction with paywall detection and fallback to RSS summary.
"""
from __future__ import annotations

import logging
from typing import Optional
import re

import requests
import trafilatura


logger = logging.getLogger(__name__)

# Request configuration
REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (compatible; DailyDigestBot/1.0; +https://github.com/yourusername/daily-reads)"

# Paywall detection patterns
PAYWALL_CUES = [
    r"subscribe to continue",
    r"sign in to continue",
    r"this content is for subscribers",
    r"subscription required",
    r"metered paywall",
    r"become a member",
    r"members only",
    r"premium content",
    r"登録が必要です",  # Japanese: registration required
    r"続きを読むには",  # Japanese: to continue reading
]

PAYWALL_PATTERN = re.compile("|".join(PAYWALL_CUES), re.IGNORECASE)


def is_paywalled(html: str, status_code: int) -> bool:
    """
    Detect if content is behind a paywall using heuristics.

    Checks:
    - HTTP status codes (402, 403)
    - Common paywall text patterns
    - Combination of very short content + paywall keywords
    """
    # Check status codes
    if status_code in (402, 403):
        return True

    # Check for paywall patterns in text
    if PAYWALL_PATTERN.search(html):
        return True

    # If content is very short (<500 chars) and contains subscription-related keywords
    if len(html) < 500:
        subscription_keywords = ["subscribe", "subscription", "sign in", "member"]
        lower_html = html.lower()
        if any(kw in lower_html for kw in subscription_keywords):
            return True

    return False


def extract_article_text(url: str, rss_summary: Optional[str] = None) -> tuple[Optional[str], str]:
    """
    Extract article text from URL.

    Returns:
        (text, status) where status is one of:
        - "ok" - extraction succeeded
        - "paywall" - detected paywall
        - "fetch_failed" - HTTP request failed
        - "extraction_failed" - couldn't extract meaningful content
        - "too_short" - extracted text too short and no RSS summary available
        - "fallback_rss" - used RSS summary as fallback

    If extraction fails but rss_summary is provided, falls back to RSS summary.
    """
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True
        )
        status_code = response.status_code

        if status_code != 200:
            logger.warning(f"HTTP {status_code} for {url}")
            if rss_summary:
                return rss_summary, "fallback_rss"
            return None, "fetch_failed"

        html = response.text

        # Check for paywall
        if is_paywalled(html, status_code):
            logger.info(f"Paywall detected: {url}")
            return None, "paywall"

        # Extract with trafilatura
        extracted = trafilatura.extract(html, include_comments=False, include_tables=False)

        if not extracted:
            logger.warning(f"Trafilatura extraction failed: {url}")
            if rss_summary:
                return rss_summary, "fallback_rss"
            return None, "extraction_failed"

        # Check minimum length
        if len(extracted) < 800:
            logger.warning(f"Extracted text too short ({len(extracted)} chars): {url}")
            if rss_summary and len(rss_summary) >= 200:
                return rss_summary, "fallback_rss"
            elif rss_summary:
                # Both too short
                return None, "too_short"
            else:
                return None, "too_short"

        return extracted, "ok"

    except requests.RequestException as e:
        logger.warning(f"Request failed for {url}: {e}")
        if rss_summary:
            return rss_summary, "fallback_rss"
        return None, "fetch_failed"
    except Exception as e:
        logger.error(f"Unexpected error extracting {url}: {e}")
        if rss_summary:
            return rss_summary, "fallback_rss"
        return None, "extraction_failed"
