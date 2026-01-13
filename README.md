# Daily Reads

Automated daily digest of curated articles on LLMs, AI, and Financial Markets.

This repository automatically generates a daily digest containing:
- 1 article about Large Language Models (LLMs)
- 1 article about AI (broader industry and engineering)
- 1 article about Financial Markets

Articles are sourced from curated RSS feeds and Google News, extracted and summarized using Gemini AI, with duplicate detection and paywall filtering.

## Latest Digest

<!-- DIGEST:START -->
*Digest will appear here after first run*
<!-- DIGEST:END -->

## History

See the [digests/](./digests/) folder for all past digests.

## How It Works

1. **Daily Schedule**: Runs automatically via GitHub Actions at 06:07 UTC every day
2. **Article Discovery**: Fetches from curated RSS feeds + Google News RSS fallbacks
3. **Quality Control**:
   - Deduplicates using SQLite (never repeats a URL)
   - Detects and skips paywalled content
   - Extracts full article text or falls back to RSS summary
   - Scores articles by relevance
4. **AI Summarization**: Uses Gemini to select best articles and generate 3 bullet-point summaries
5. **Output**: Updates this README and creates `digests/YYYY-MM-DD.md` files

## Want Your Own?

If you'd like to fork this and run your own daily digest:

1. Fork this repository
2. Get a Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
3. Add it to your repository secrets:
   - Go to Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `GEMINI_API_KEY`
   - Value: Your Gemini API key
4. The workflow will run automatically every day at 06:07 UTC
5. Customize feeds in `src/feeds.py` if desired

## Features

- Never repeats the same article URL
- Detects and skips paywalled content
- Minimizes arXiv papers (prefers mainstream sources)
- Falls back to RSS summaries when full-text extraction fails
- Expands time window (48h → 7d) if insufficient candidates
- Shows source pool used and rejected candidates for transparency
- Runs on weekends too
- Low cost (uses Gemini Flash model)
