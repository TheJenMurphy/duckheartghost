#!/usr/bin/env python3
"""
iHeartClean Pipeline - Main Orchestrator
Scrape → Classify → Push to Webflow

Usage:
  # Single product
  python pipeline.py "https://brand.com/product" --push
  
  # Batch from file
  python pipeline.py urls.txt --push --output results.json
  
  # Classify only (no push)
  python pipeline.py "https://brand.com/product"
  
  # With AI enhancement
  python pipeline.py "https://brand.com/product" --push --ai
"""

import json
import sys
import os
import time
import argparse
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Install dependencies:")
    print("  pip install requests beautifulsoup4 python-dotenv --break-system-packages")
    sys.exit(1)

# Import local modules
from classifier import classify_product, detect_attributes, extract_product_data
from webflow_client import WebflowClient, WebflowConfig, product_to_webflow_fields

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# =============================================================================
# SCRAPER
# =============================================================================

def scrape_product_page(url: str, timeout: int = 15) -> dict:
    """
    Scrape product page and extract text content.
    Cost: FREE
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {"error": str(e), "url": url}
    
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Remove non-content elements
    for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer"]):
        tag.decompose()
    
    # Extract text
    text = soup.get_text(separator=" ", strip=True)
    
    # Extract title
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)
    
    # Try to extract brand from common patterns
    brand = ""
    meta_brand = soup.find("meta", {"property": "og:site_name"})
    if meta_brand:
        brand = meta_brand.get("content", "")
    
    # Try to find ingredients
    ingredients = ""
    ing_section = soup.find(string=lambda t: t and "ingredients" in t.lower() if t else False)
    if ing_section:
        parent = ing_section.find_parent()
        if parent:
            next_elem = parent.find_next_sibling()
            if next_elem:
                ingredients = next_elem.get_text(strip=True)[:500]
    
    return {
        "url": url,
        "domain": urlparse(url).netloc,
        "title": title,
        "brand": brand,
        "text": text[:50000],  # Limit for processing
        "ingredients": ingredients,
    }


# =============================================================================
# AI ENHANCEMENT (Optional)
# =============================================================================

def enhance_with_ai(product_data: dict, scraped_text: str) -> dict:
    """
    Optional AI enhancement using Claude API.
    Cost: ~$0.001-0.01 per product
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  Skipping AI enhancement (no ANTHROPIC_API_KEY)")
        return product_data
    
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 500,
                "messages": [{
                    "role": "user",
                    "content": f"""Analyze this beauty product and provide:
1. A 1-sentence product summary (max 150 chars)
2. Top 3 key benefits
3. Any safety concerns

Product: {product_data.get('name', 'Unknown')}
Text excerpt: {scraped_text[:2000]}

Respond in JSON format:
{{"summary": "...", "benefits": ["...", "...", "..."], "concerns": ["..."]}}"""
                }]
            },
            timeout=30,
        )
        resp.raise_for_status()
        
        result = resp.json()
        content = result.get("content", [{}])[0].get("text", "{}")
        
        # Parse AI response
        try:
            ai_data = json.loads(content)
            product_data["ai_summary"] = ai_data.get("summary", "")
            product_data["ai_benefits"] = ai_data.get("benefits", [])
            product_data["ai_concerns"] = ai_data.get("concerns", [])
            product_data["ai_enhanced"] = True
        except json.JSONDecodeError:
            pass
            
    except Exception as e:
        print(f"  AI enhancement failed: {e}")
    
    return product_data


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def process_product(url: str, use_ai: bool = False, push_to_webflow: bool = False,
                    webflow_client: WebflowClient = None) -> dict:
    """
    Process single product through full pipeline.
    
    Returns classified product data, optionally pushes to Webflow.
    """
    print(f"\n{'='*60}")
    print(f"Processing: {url}")
    print(f"{'='*60}")
    
    # Step 1: Scrape (FREE)
    print("1. Scraping page...")
    scraped = scrape_product_page(url)
    
    if "error" in scraped:
        print(f"   Error: {scraped['error']}")
        return {"error": scraped["error"], "url": url}
    
    print(f"   Title: {scraped['title'][:50]}...")
    print(f"   Brand: {scraped['brand'] or 'Unknown'}")
    
    # Step 2: Classify (FREE)
    print("2. Classifying (local regex)...")
    product = classify_product(
        text=scraped["text"],
        product_name=scraped["title"],
        brand=scraped["brand"],
    )
    product["url"] = url
    product["ingredients_raw"] = scraped.get("ingredients", "")
    
    print(f"   Detected {product['attribute_count']} attributes")
    print(f"   Overall score: {product['overall_score']}/5")
    print(f"   Best for: {', '.join(product['best_for']) or 'General'}")
    
    # Step 3: AI Enhancement (Optional, ~$0.001)
    if use_ai:
        print("3. Enhancing with AI...")
        product = enhance_with_ai(product, scraped["text"])
        if product.get("ai_enhanced"):
            print(f"   Summary: {product.get('ai_summary', '')[:60]}...")
    
    # Step 4: Push to Webflow (FREE within plan)
    if push_to_webflow and webflow_client:
        print("4. Pushing to Webflow...")
        try:
            field_data = product_to_webflow_fields(product)
            result = webflow_client.upsert_item(field_data)
            product["webflow_id"] = result.get("id")
            product["webflow_status"] = "pushed"
            print(f"   ✓ Pushed: {result.get('id')}")
        except Exception as e:
            product["webflow_status"] = f"error: {e}"
            print(f"   ✗ Error: {e}")
    
    # Cost summary
    cost = 0.001 if use_ai else 0
    product["estimated_cost"] = f"${cost:.3f}"
    print(f"\n   Cost: ${cost:.3f}")
    
    return product


def process_batch(urls: list, use_ai: bool = False, push_to_webflow: bool = False,
                  webflow_client: WebflowClient = None, max_workers: int = 3) -> dict:
    """
    Process multiple URLs.
    """
    print(f"\n{'#'*60}")
    print(f"BATCH PROCESSING: {len(urls)} products")
    print(f"{'#'*60}")
    
    results = []
    failed = []
    
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}]")
        try:
            result = process_product(url, use_ai, push_to_webflow, webflow_client)
            if "error" not in result:
                results.append(result)
            else:
                failed.append(result)
        except Exception as e:
            failed.append({"url": url, "error": str(e)})
            print(f"Failed: {e}")
        
        # Rate limit buffer
        if push_to_webflow:
            time.sleep(1)
        else:
            time.sleep(0.5)
    
    # Summary
    total_cost = sum(float(r.get("estimated_cost", "$0").replace("$", "")) for r in results)
    
    return {
        "products": results,
        "failed": failed,
        "summary": {
            "total": len(urls),
            "success": len(results),
            "failed": len(failed),
            "total_cost": f"${total_cost:.3f}",
        }
    }


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="iHeartClean Pipeline: Scrape → Classify → Push to Webflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single product, classify only
  python pipeline.py "https://tower28beauty.com/products/sunnydays"
  
  # Single product, push to Webflow
  python pipeline.py "https://tower28beauty.com/products/sunnydays" --push
  
  # Batch from file
  python pipeline.py urls.txt --push --output results.json
  
  # With AI enhancement
  python pipeline.py "https://example.com/product" --ai --push

Environment Variables:
  WEBFLOW_API_TOKEN     - Webflow API token (required for --push)
  WEBFLOW_SITE_ID       - Webflow site ID (required for --push)
  WEBFLOW_COLLECTION_ID - Products collection ID (required for --push)
  ANTHROPIC_API_KEY     - Claude API key (required for --ai)
        """
    )
    
    parser.add_argument("input", help="Product URL or file containing URLs (one per line)")
    parser.add_argument("--push", action="store_true", help="Push to Webflow CMS")
    parser.add_argument("--ai", action="store_true", help="Enable AI enhancement (~$0.001/product)")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--workers", type=int, default=3, help="Parallel workers for batch")
    
    args = parser.parse_args()
    
    # Determine if input is URL or file
    if args.input.startswith("http"):
        urls = [args.input]
    elif Path(args.input).exists():
        with open(args.input, "r") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        print(f"Loaded {len(urls)} URLs from {args.input}")
    else:
        print(f"Error: '{args.input}' is not a valid URL or file")
        sys.exit(1)
    
    # Setup Webflow client if pushing
    webflow_client = None
    if args.push:
        config = WebflowConfig.from_env()
        if not config.api_token:
            print("Error: WEBFLOW_API_TOKEN not set")
            print("Set environment variables or create .env file")
            sys.exit(1)
        webflow_client = WebflowClient(config)
        print("Webflow client initialized")
    
    # Process
    if len(urls) == 1:
        result = process_product(urls[0], args.ai, args.push, webflow_client)
        results = {"products": [result] if "error" not in result else [], 
                   "failed": [result] if "error" in result else []}
    else:
        results = process_batch(urls, args.ai, args.push, webflow_client, args.workers)
    
    # Output
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    else:
        print("\n" + "="*60)
        print("RESULTS")
        print("="*60)
        print(json.dumps(results, indent=2))
    
    # Summary
    if "summary" in results:
        s = results["summary"]
        print(f"\n{'='*60}")
        print(f"SUMMARY: {s['success']}/{s['total']} succeeded, Cost: {s['total_cost']}")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
