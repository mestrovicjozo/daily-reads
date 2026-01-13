# src/render.py
"""
Markdown rendering for daily digests.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict, List, Optional
import re


def render_digest(
    digest_date: date,
    articles: Dict[str, Optional[dict]],
    source_pools: Dict[str, List[str]],
    rejections: List[tuple[str, str]]
) -> str:
    """
    Render a daily digest as markdown.

    Args:
        digest_date: The date for this digest
        articles: Dict mapping category -> article dict (or None if no article found)
                 Article dict should have: title, url, bullets
        source_pools: Dict mapping category -> list of source names used
        rejections: List of (url, reason) tuples for rejected candidates

    Returns:
        Markdown string
    """
    lines = []

    # Header
    lines.append(f"# Daily Digest — {digest_date}")
    lines.append("")

    # Category mapping for display
    category_titles = {
        "llms": "LLMs",
        "ai": "AI",
        "markets": "Financial Markets"
    }

    # Article sections
    for category in ["llms", "ai", "markets"]:
        title = category_titles[category]
        lines.append(f"## {title}")

        article = articles.get(category)
        if article:
            lines.append(f"Title: [{article['title']}]({article['url']})")
            lines.append("Key takeaways:")
            for bullet in article.get("bullets", []):
                lines.append(f"- {bullet}")
        else:
            lines.append("*No suitable article found*")

        lines.append("")

    # Source pool section
    lines.append("## Source pool used today")
    for category in ["llms", "ai", "markets"]:
        title = category_titles[category]
        sources = source_pools.get(category, [])
        sources_str = ", ".join(sources) if sources else "None"
        lines.append(f"- {title}: {sources_str}")
    lines.append("")

    # Rejections section
    lines.append("## Rejected candidates (why)")
    if rejections:
        # Limit to 15 most interesting rejections
        for url, reason in rejections[:15]:
            # Shorten URL for readability
            display_url = _shorten_url(url)
            lines.append(f"- {display_url} — {reason}")
    else:
        lines.append("- None")
    lines.append("")

    return "\n".join(lines)


def _shorten_url(url: str, max_len: int = 80) -> str:
    """Shorten URL for display if it's too long."""
    if len(url) <= max_len:
        return url
    return url[:max_len - 3] + "..."


def update_readme(readme_path: Path, digest_content: str) -> None:
    """
    Update README.md with the latest digest content between markers.

    Markers:
        <!-- DIGEST:START -->
        ...
        <!-- DIGEST:END -->

    If markers don't exist, they will be appended at the end.
    """
    start_marker = "<!-- DIGEST:START -->"
    end_marker = "<!-- DIGEST:END -->"

    if readme_path.exists():
        content = readme_path.read_text(encoding="utf-8")
    else:
        # Create basic README structure
        content = """# Daily Reads

Automated daily digest of curated articles on LLMs, AI, and Financial Markets.

## Latest Digest

<!-- DIGEST:START -->
<!-- DIGEST:END -->

## History

See the [digests/](./digests/) folder for all past digests.

## Setup

This digest is automatically generated using:
- Python 3.11+
- Gemini API for summarization
- RSS feeds + Google News RSS
- GitHub Actions (runs daily at 06:07 UTC)

### Running locally

1. Set up environment:
```bash
python -m venv venv
source venv/bin/activate  # or venv\\Scripts\\activate on Windows
pip install -r requirements.txt
```

2. Set your Gemini API key:
```bash
export GEMINI_API_KEY='your-key-here'
```

3. Run the digest:
```bash
python -m src.run_digest
```

### GitHub Actions setup

Add `GEMINI_API_KEY` to your repository secrets (Settings → Secrets and variables → Actions).
"""

    # Find marker positions
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx != -1 and end_idx != -1:
        # Replace content between markers
        new_content = (
            content[:start_idx + len(start_marker)] +
            "\n" + digest_content + "\n" +
            content[end_idx:]
        )
    else:
        # Markers don't exist, append at end
        new_content = content.rstrip() + f"\n\n{start_marker}\n{digest_content}\n{end_marker}\n"

    readme_path.write_text(new_content, encoding="utf-8")
