# src/utils.py
"""
Utility functions for URL normalization, date parsing, etc.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import logging

import dateutil.parser


logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """
    Normalize URL by removing common tracking parameters.

    This helps detect duplicates when the same article appears with different UTM params.
    """
    parsed = urlparse(url)

    # Remove common tracking params
    tracking_params = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
        'fbclid', 'gclid', 'msclkid', 'mc_cid', 'mc_eid',
        '_ga', '_gl', 'ref', 'source'
    }

    if parsed.query:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        cleaned_qs = {k: v for k, v in qs.items() if k not in tracking_params}
        new_query = urlencode(cleaned_qs, doseq=True)
    else:
        new_query = ''

    # Reconstruct URL
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        ''  # remove fragment
    ))

    # Remove trailing slash for consistency (unless it's the root)
    if normalized.endswith('/') and parsed.path != '/':
        normalized = normalized.rstrip('/')

    return normalized


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse an RSS/Atom date string into a timezone-aware datetime.

    Returns None if parsing fails or date_str is None.
    """
    if not date_str:
        return None

    try:
        dt = dateutil.parser.parse(date_str)
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None


def is_recent(published_dt: Optional[datetime], cutoff_dt: datetime) -> bool:
    """
    Check if a published datetime is more recent than a cutoff.

    Returns False if published_dt is None.
    """
    if published_dt is None:
        return False
    return published_dt >= cutoff_dt
