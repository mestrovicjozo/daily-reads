# src/gemini_summarize.py
"""
Gemini-based article summarization into bullet points.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional
import re

import google.generativeai as genai


logger = logging.getLogger(__name__)


def init_gemini(api_key: Optional[str] = None, model_name: str = "gemini-2.0-flash-exp") -> genai.GenerativeModel:
    """
    Initialize Gemini client.

    Args:
        api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
        model_name: Model to use (defaults to MODEL_NAME env var or gemini-2.0-flash-exp)

    Returns:
        Configured GenerativeModel instance
    """
    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment")

    # Allow override via env var
    model_name = os.getenv("MODEL_NAME", model_name)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    return model


def summarize_article(article_text: str, model: Optional[genai.GenerativeModel] = None) -> List[str]:
    """
    Summarize an article into exactly 3 bullet points using Gemini.

    Args:
        article_text: The full article text to summarize
        model: Pre-initialized Gemini model (if None, will initialize)

    Returns:
        List of 3 bullet point strings (without leading "- " or "• ")

    Falls back to heuristic extraction if Gemini fails.
    """
    if model is None:
        try:
            model = init_gemini()
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            return _fallback_bullets(article_text)

    # Construct prompt
    prompt = f"""You write concise bullet summaries for a daily news digest. Do not invent facts not present in the provided text.

Here is the article text:

{article_text[:8000]}

Produce exactly 3 bullet points of key takeaways. Keep each bullet under 25 words. Output only the bullet points, one per line, without numbering or bullet symbols."""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Parse bullets
        bullets = _parse_bullets(text)

        if len(bullets) != 3:
            logger.warning(f"Gemini returned {len(bullets)} bullets instead of 3, using fallback")
            return _fallback_bullets(article_text)

        return bullets

    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return _fallback_bullets(article_text)


def _parse_bullets(text: str) -> List[str]:
    """
    Parse bullet points from Gemini response.

    Handles various formats:
    - Bullet points with "- " or "• " or "* "
    - Numbered lists "1. " or "1) "
    - Plain lines
    """
    lines = text.strip().split('\n')
    bullets = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Remove leading markers
        line = re.sub(r'^[-•*]\s+', '', line)  # bullet markers
        line = re.sub(r'^\d+[\.)]\s+', '', line)  # numbered lists

        if line:
            bullets.append(line)

    return bullets


def _fallback_bullets(article_text: str) -> List[str]:
    """
    Generate conservative fallback bullets when Gemini fails.

    Simply extracts first few sentences as bullets.
    """
    # Split into sentences (very basic)
    sentences = re.split(r'[.!?]+\s+', article_text[:1500])
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    # Take first 3 sentences, truncate if too long
    bullets = []
    for sent in sentences[:3]:
        if len(sent) > 150:
            sent = sent[:147] + "..."
        bullets.append(sent)

    # Pad if needed
    while len(bullets) < 3:
        bullets.append("Key information available in full article.")

    return bullets
