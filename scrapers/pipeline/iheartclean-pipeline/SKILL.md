---
name: iheartclean-pipeline
description: End-to-end product scraping, 9S classification, and Webflow CMS publishing for iHeartClean.beauty. Uses Python for scraping/classification, Webflow API for direct CMS updates, and optional ChatGPT/Claude API for AI-enhanced analysis. Triggers on "scrape product", "classify product", "push to Webflow", "9S analysis", or iHeartClean workflow requests.
---

# iHeartClean Pipeline

Complete Python → Webflow workflow. No Make.com.

## Architecture

```
[Product URL] → [Python Scraper] → [Local Classifier] → [Webflow API]
                                          ↓
                            [Optional: Claude/GPT API for deep analysis]
```

## Cost Structure

| Component | Cost |
|-----------|------|
| Python scraping | FREE |
| Local regex classification | FREE |
| Webflow API | FREE (within plan limits) |
| Claude Haiku (optional) | ~$0.001/product |
| ChatGPT-4o-mini (optional) | ~$0.001/product |

**Total: $0.00-0.002 per product**

## Quick Start

### 1. Setup
```bash
pip install requests beautifulsoup4 python-dotenv --break-system-packages
```

### 2. Configure Webflow API
Create `.env` file:
```
WEBFLOW_API_TOKEN=your_token_here
WEBFLOW_COLLECTION_ID=your_collection_id
ANTHROPIC_API_KEY=optional_for_ai_analysis
```

### 3. Single Product
```bash
python scripts/pipeline.py "https://brand.com/product" --push
```

### 4. Batch Processing
```bash
python scripts/pipeline.py urls.txt --push --output results.json
```

## Scripts

| Script | Purpose |
|--------|---------|
| `pipeline.py` | Main workflow: scrape → classify → push |
| `webflow_client.py` | Webflow API wrapper |
| `classifier.py` | Local 9S classification |
| `ai_enhancer.py` | Optional Claude/GPT integration |

## References

- `references/attribute-patterns.md` - 150+ regex patterns
- `references/persona-priorities.md` - Research-backed scoring
- `references/webflow-setup.md` - CMS configuration guide

## ChatGPT Custom GPT

See `assets/chatgpt-instructions.md` for custom GPT configuration that can:
- Analyze product ingredients
- Generate product descriptions
- Suggest persona targeting
