#!/usr/bin/env python3
"""
Brand Scraper - Discover and process entire product lines from collection URLs.

Usage:
  # Scrape entire brand collection
  python brand_scraper.py "https://kosas.com/collections/all" --push

  # Limit to N products (for testing)
  python brand_scraper.py "https://brand.com/collections/all" --limit 10

  # Just discover URLs without processing
  python brand_scraper.py "https://brand.com/collections/all" --discover-only -o urls.json

  # With AI enhancement
  python brand_scraper.py "https://brand.com/collections/all" --ai --push
"""

import json
import sys
import os
import time
import re
import argparse
from pathlib import Path
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Optional, Tuple

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Install dependencies:")
    print("  pip install requests beautifulsoup4 python-dotenv")
    sys.exit(1)

# Import local modules
from classifier import classify_product
from webflow_client import WebflowClient, WebflowConfig, product_to_webflow_fields

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# =============================================================================
# AI ENHANCEMENT (Claude API)
# =============================================================================

def ai_enhance_product(product_data: Dict) -> Dict:
    """
    Use Claude to analyze product and generate rich drawer content.
    Returns enhanced fields for Webflow CMS.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("      No ANTHROPIC_API_KEY - skipping AI enhancement")
        return {}

    # Build context from available data
    name = product_data.get("title") or product_data.get("name", "")
    brand = product_data.get("vendor") or product_data.get("brand", "")
    description = product_data.get("body_text", "")
    tags = product_data.get("tags", [])
    if isinstance(tags, list):
        tags = ", ".join(tags)
    price = product_data.get("price", "")

    prompt = f"""Analyze this clean beauty product and provide structured information.

PRODUCT: {name}
BRAND: {brand}
PRICE: ${price}
TAGS: {tags}
DESCRIPTION: {description}

Respond in this exact JSON format (no markdown, just JSON):
{{
  "what_it_is": "2-3 sentences describing what this product is and its main benefits",
  "who_its_for": "Who should use this product (skin types, concerns, lifestyles)",
  "how_to_use": "Brief application instructions",
  "whats_in_it": "Key ingredients and their benefits (if known from description)",
  "whats_it_in": "Product format/packaging (e.g., 'Glass bottle with dropper')",
  "product_type": "Category like 'Cleanser', 'Serum', 'Moisturizer', 'Mask', etc.",
  "category": "Broader category like 'Skincare', 'Makeup', 'Body Care', 'Hair Care'",
  "formulation": "Product texture like 'Cream', 'Gel', 'Oil', 'Serum', 'Balm'",
  "skin_types": "Suitable skin types (e.g., 'All skin types', 'Dry, sensitive')",
  "detected_claims": ["list", "of", "marketing", "claims", "like", "vegan", "cruelty-free", "clean", "dermatologist-tested"]
}}

Focus on clean beauty attributes. If information isn't available, make reasonable inferences based on the brand and product type."""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        resp.raise_for_status()

        content = resp.json()["content"][0]["text"]
        # Parse JSON from response
        enhanced = json.loads(content)
        return enhanced

    except Exception as e:
        print(f"      AI enhancement error: {e}")
        return {}


# =============================================================================
# PLATFORM DETECTION
# =============================================================================

def detect_platform(url: str, html: str = "") -> str:
    """Detect e-commerce platform from URL or HTML."""
    domain = urlparse(url).netloc.lower()

    # Check URL patterns
    if "shopify" in domain or "myshopify" in domain:
        return "shopify"

    # Check HTML for platform signatures
    if html:
        html_lower = html.lower()
        if "shopify" in html_lower or "cdn.shopify.com" in html_lower:
            return "shopify"
        if "woocommerce" in html_lower or "wp-content" in html_lower:
            return "woocommerce"
        if "magento" in html_lower:
            return "magento"

    # Try Shopify products.json endpoint
    try:
        test_url = f"https://{domain}/products.json?limit=1"
        resp = requests.get(test_url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200 and "products" in resp.text:
            return "shopify"
    except:
        pass

    return "generic"


# =============================================================================
# SHOPIFY SCRAPER (Fast mode using JSON API)
# =============================================================================

def fetch_shopify_product_detail(domain: str, handle: str) -> Dict:
    """
    Fetch individual product JSON to get full body_html.
    The collection endpoint doesn't always include body_html.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    url = f"https://{domain}/products/{handle}.json"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json().get("product", {})
    except Exception as e:
        return {}


def scrape_shopify_collection(base_url: str, limit: int = None) -> List[Dict]:
    """
    Scrape Shopify store using products.json API.
    Much faster than HTML scraping - gets 250 products per request.
    """
    domain = urlparse(base_url).netloc
    products = []
    page = 1

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    print(f"  Using Shopify JSON API (fast mode)")

    while True:
        url = f"https://{domain}/products.json?limit=250&page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  Error fetching page {page}: {e}")
            break

        page_products = data.get("products", [])
        if not page_products:
            break

        for p in page_products:
            product = {
                "url": f"https://{domain}/products/{p.get('handle', '')}",
                "title": p.get("title", ""),
                "handle": p.get("handle", ""),
                "vendor": p.get("vendor", ""),
                "product_type": p.get("product_type", ""),
                "tags": p.get("tags", []),
                "images": [img.get("src", "") for img in p.get("images", [])[:10]],
                "main_image": p.get("images", [{}])[0].get("src", "") if p.get("images") else "",
                "variants": p.get("variants", []),
                "body_html": p.get("body_html", ""),
            }

            # Extract price from first variant
            if product["variants"]:
                product["price"] = float(product["variants"][0].get("price", 0))

            products.append(product)

            if limit and len(products) >= limit:
                return products

        print(f"  Fetched page {page}: {len(page_products)} products (total: {len(products)})")
        page += 1
        time.sleep(0.5)  # Rate limit

    return products


# =============================================================================
# GENERIC HTML SCRAPER
# =============================================================================

def scrape_collection_html(collection_url: str, limit: int = None) -> List[str]:
    """
    Scrape product URLs from HTML collection page.
    Handles pagination for various platforms.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }

    product_urls = set()
    urls_to_scrape = [collection_url]
    scraped_urls = set()

    while urls_to_scrape:
        url = urls_to_scrape.pop(0)
        if url in scraped_urls:
            continue
        scraped_urls.add(url)

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        domain = urlparse(url).netloc

        # Find product links - common patterns
        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Shopify pattern
            if "/products/" in href and "/collections/" not in href:
                full_url = urljoin(url, href).split("?")[0]
                product_urls.add(full_url)

            # WooCommerce pattern
            elif "/product/" in href:
                full_url = urljoin(url, href).split("?")[0]
                product_urls.add(full_url)

        # Find pagination links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "page=" in href or "/page/" in href:
                next_url = urljoin(url, href)
                if next_url not in scraped_urls:
                    urls_to_scrape.append(next_url)

        print(f"  Found {len(product_urls)} product URLs so far...")

        if limit and len(product_urls) >= limit:
            break

        time.sleep(0.5)

    return list(product_urls)[:limit] if limit else list(product_urls)


# =============================================================================
# PRODUCT SCRAPER
# =============================================================================

def scrape_product_page(url: str, timeout: int = 15) -> Dict:
    """Scrape individual product page for full details."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        return {"error": str(e), "url": url}

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove non-content
    for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer"]):
        tag.decompose()

    # Extract text
    text = soup.get_text(separator=" ", strip=True)

    # Title
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)

    # Brand
    brand = ""
    meta_brand = soup.find("meta", {"property": "og:site_name"})
    if meta_brand:
        brand = meta_brand.get("content", "")

    # Images
    images = []
    main_image = ""

    # OG image
    og_img = soup.find("meta", {"property": "og:image"})
    if og_img:
        main_image = og_img.get("content", "")
        images.append(main_image)

    # Product images
    for img in soup.find_all("img"):
        src = img.get("src", "") or img.get("data-src", "")
        if src and "product" in src.lower():
            if src.startswith("//"):
                src = "https:" + src
            if src not in images:
                images.append(src)

    # Ingredients
    ingredients = ""
    ing_patterns = [
        r"ingredients?[:]\s*(.{50,1000})",
        r"full ingredients?[:]\s*(.{50,1000})",
    ]
    for pattern in ing_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            ingredients = match.group(1)[:500]
            break

    # Price
    price = None
    price_match = re.search(r"\$(\d+(?:\.\d{2})?)", text)
    if price_match:
        price = float(price_match.group(1))

    return {
        "url": url,
        "domain": urlparse(url).netloc,
        "title": title,
        "brand": brand,
        "text": text[:50000],
        "ingredients": ingredients,
        "main_image": main_image,
        "images": images[:10],
        "price": price,
    }


# =============================================================================
# MAIN PROCESSING
# =============================================================================

def process_shopify_product(product: Dict, use_ai: bool = False) -> Dict:
    """Process a Shopify product from JSON API data."""
    # If body_html is empty, fetch individual product JSON for full details
    body_html = product.get("body_html", "")
    if not body_html and product.get("handle"):
        domain = urlparse(product.get("url", "")).netloc
        if domain:
            detail = fetch_shopify_product_detail(domain, product["handle"])
            if detail:
                body_html = detail.get("body_html", "")
                # Also grab tags if missing
                if not product.get("tags") and detail.get("tags"):
                    product["tags"] = detail.get("tags", [])

    # Clean HTML from body
    body_text = ""
    if body_html:
        soup = BeautifulSoup(body_html, "html.parser")
        body_text = soup.get_text(separator=" ", strip=True)

    # Combine all text for classification
    tags = product.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    full_text = " ".join([
        product.get("title", ""),
        product.get("vendor", ""),
        product.get("product_type", ""),
        " ".join(tags),
        body_text,
    ])

    # Classify
    classified = classify_product(
        text=full_text,
        product_name=product.get("title", ""),
        brand=product.get("vendor", ""),
    )

    # Add Shopify-specific data
    classified["url"] = product.get("url", "")
    classified["main_image"] = product.get("main_image", "")
    classified["images"] = product.get("images", [])
    classified["price"] = product.get("price")
    classified["ingredients_raw"] = body_text[:500] if "ingredient" in body_text.lower() else ""
    classified["raw_text"] = full_text[:1000]  # Store for debugging

    # AI Enhancement - generate rich drawer content
    if use_ai:
        ai_data = ai_enhance_product({
            "title": product.get("title", ""),
            "vendor": product.get("vendor", ""),
            "body_text": body_text,
            "tags": product.get("tags", []),
            "price": product.get("price", ""),
        })

        if ai_data:
            # Add 5 drawer fields
            classified["what_it_is"] = ai_data.get("what_it_is", "")
            classified["who_its_for"] = ai_data.get("who_its_for", "")
            classified["how_to_use"] = ai_data.get("how_to_use", "")
            classified["whats_in_it"] = ai_data.get("whats_in_it", "")
            classified["whats_it_in"] = ai_data.get("whats_it_in", "")

            # Add classification fields
            classified["product_type"] = ai_data.get("product_type", "")
            classified["category"] = ai_data.get("category", "")
            classified["formulation"] = ai_data.get("formulation", "")
            classified["skin_types"] = ai_data.get("skin_types", "")

            # Merge AI-detected claims with regex-detected attributes
            ai_claims = ai_data.get("detected_claims", [])
            if ai_claims:
                # Normalize claims to match classifier format
                normalized = [c.lower().replace("-", "_").replace(" ", "_") for c in ai_claims]
                existing = classified.get("detected_attributes", [])
                merged = list(set(existing + normalized))
                classified["detected_attributes"] = merged
                classified["attribute_count"] = len(merged)

    return classified


def process_scraped_product(url: str, use_ai: bool = False) -> Dict:
    """Process a product by scraping its page."""
    scraped = scrape_product_page(url)

    if "error" in scraped:
        return {"error": scraped["error"], "url": url}

    classified = classify_product(
        text=scraped["text"],
        product_name=scraped["title"],
        brand=scraped["brand"],
    )

    classified["url"] = url
    classified["main_image"] = scraped.get("main_image", "")
    classified["images"] = scraped.get("images", [])
    classified["price"] = scraped.get("price")
    classified["ingredients_raw"] = scraped.get("ingredients", "")

    return classified


def scrape_brand(collection_url: str, limit: int = None, use_ai: bool = False,
                 push_to_webflow: bool = False, webflow_client: WebflowClient = None,
                 discover_only: bool = False) -> Dict:
    """
    Main function: Scrape and process entire brand from collection URL.
    """
    print(f"\n{'#'*60}")
    print(f"BRAND SCRAPER")
    print(f"Collection: {collection_url}")
    print(f"{'#'*60}\n")

    # Detect platform
    print("1. Detecting platform...")
    platform = detect_platform(collection_url)
    print(f"   Platform: {platform}")

    # Discover products
    print("\n2. Discovering products...")

    if platform == "shopify":
        products_data = scrape_shopify_collection(collection_url, limit)
        product_urls = [p["url"] for p in products_data]
    else:
        product_urls = scrape_collection_html(collection_url, limit)
        products_data = None

    print(f"   Found {len(product_urls)} products")

    if discover_only:
        return {
            "collection_url": collection_url,
            "platform": platform,
            "product_count": len(product_urls),
            "product_urls": product_urls,
        }

    # Process products
    print(f"\n3. Processing {len(product_urls)} products...")

    results = []
    failed = []

    for i, url in enumerate(product_urls, 1):
        print(f"\n   [{i}/{len(product_urls)}] {url[:60]}...")

        try:
            if platform == "shopify" and products_data:
                # Use pre-fetched Shopify data
                product = products_data[i-1]
                classified = process_shopify_product(product, use_ai)
            else:
                # Scrape individual page
                classified = process_scraped_product(url, use_ai)

            if "error" in classified:
                failed.append(classified)
                print(f"      Error: {classified['error']}")
                continue

            print(f"      Score: {classified['overall_score']}/5, Attributes: {classified['attribute_count']}")

            # Push to Webflow
            if push_to_webflow and webflow_client:
                try:
                    # Look up brand ID
                    brand_name = classified.get("brand", "")
                    brand_id = webflow_client.find_brand_id(brand_name) if brand_name else None

                    if not brand_id:
                        print(f"      Warning: Brand '{brand_name}' not found in Webflow - skipping push")
                        print(f"      Create the brand in Webflow CMS first, then retry")
                        classified["webflow_status"] = f"skipped: brand '{brand_name}' not in Webflow"
                    else:
                        field_data = product_to_webflow_fields(classified, brand_id=brand_id)
                        result = webflow_client.upsert_item(field_data)
                        classified["webflow_id"] = result.get("id")
                        classified["webflow_status"] = "pushed"
                        print(f"      Pushed to Webflow: {result.get('id')}")
                except Exception as e:
                    classified["webflow_status"] = f"error: {e}"
                    print(f"      Webflow error: {e}")

            results.append(classified)

        except Exception as e:
            failed.append({"url": url, "error": str(e)})
            print(f"      Failed: {e}")

        # Rate limiting
        time.sleep(0.5 if platform == "shopify" else 1)

    # Summary
    print(f"\n{'='*60}")
    print(f"COMPLETE")
    print(f"{'='*60}")
    print(f"  Processed: {len(results)}/{len(product_urls)}")
    print(f"  Failed: {len(failed)}")

    return {
        "collection_url": collection_url,
        "platform": platform,
        "summary": {
            "total": len(product_urls),
            "success": len(results),
            "failed": len(failed),
        },
        "products": results,
        "failed": failed,
    }


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Scrape entire brand product line from collection URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape all products from a brand
  python brand_scraper.py "https://kosas.com/collections/all" --push

  # Limit to 10 products (testing)
  python brand_scraper.py "https://brand.com/collections/all" --limit 10

  # Just discover URLs
  python brand_scraper.py "https://brand.com/collections/all" --discover-only -o urls.json

  # With AI enhancement
  python brand_scraper.py "https://brand.com/collections/all" --ai --push
        """
    )

    parser.add_argument("collection_url", help="Collection/category URL to scrape")
    parser.add_argument("--limit", type=int, help="Limit number of products")
    parser.add_argument("--push", action="store_true", help="Push to Webflow CMS")
    parser.add_argument("--ai", action="store_true", help="Enable AI enhancement")
    parser.add_argument("--discover-only", action="store_true", help="Only discover URLs, don't process")
    parser.add_argument("--output", "-o", help="Output JSON file")

    args = parser.parse_args()

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

    # Run scraper
    results = scrape_brand(
        collection_url=args.collection_url,
        limit=args.limit,
        use_ai=args.ai,
        push_to_webflow=args.push,
        webflow_client=webflow_client,
        discover_only=args.discover_only,
    )

    # Output
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    else:
        print("\n" + json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
