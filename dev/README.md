# dev/ — Development & Testing Tools

This folder contains test scripts, debug utilities, and research notes used during development.
These files are **not required** to run InsightX.

## Contents

| File | Description |
|------|-------------|
| `test_serper_scraper.py` | Integration test for Serper API scraping (v13.1) |
| `test_full_pipeline.py` | End-to-end test: scrape → Gemini analysis |
| `test_backend.py` | Backend API endpoint tests |
| `ISSUES_RESOLVED.md` | Bug tracking & resolution history |
| `RESEARCH_google_maps_scraping.md` | Research notes on scraping approaches |

## Running Tests

```bash
# Test scraper only
python dev/test_serper_scraper.py

# Test full pipeline (scraper + Gemini)
python dev/test_full_pipeline.py
```
