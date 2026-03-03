#!/usr/bin/env python3
"""
Unified iHeartClean Pipeline
Merges Google Sheets automation and Brand Scraper into one system.

Data Sources:
1. Google Sheets (single products from Credo queue)
2. Brand URLs (bulk scrape entire brand catalogs)
3. Direct product URLs

All sources → Same classifier → Same Webflow format

Usage:
  # Single product URL
  python unified_pipeline.py "https://kosas.com/products/revealer-concealer" --push

  # Bulk brand catalog
  python unified_pipeline.py "https://kosas.com/collections/all" --brand --push

  # From Google Sheets queue (processes one pending product)
  python unified_pipeline.py --sheets --push

  # With AI enhancement (costs ~$0.001/product)
  python unified_pipeline.py "https://..." --push --ai
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, List, Optional
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Install dependencies: pip install requests beautifulsoup4 python-dotenv")
    sys.exit(1)

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import local modules
from classifier import classify_product
from webflow_client import WebflowClient, WebflowConfig, product_to_webflow_fields


# =============================================================================
# SCRAPING FUNCTIONS
# =============================================================================

def detect_url_type(url: str) -> str:
    """Detect if URL is a product page or collection page."""
    if "/collections/" in url and "/products/" not in url:
        return "collection"
    elif "/products/" in url:
        return "product"
    else:
        return "unknown"


def extract_full_ingredients(url: str) -> Optional[str]:
    """
    Scrape product page HTML to extract full INCI ingredient list.
    Returns the full ingredient list or None if not found.
    Works with products that start with Water/Aqua OR other ingredients (lipsticks, powders, etc).
    """
    import re
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "text/html",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text

        # Common cosmetic INCI ingredients (for validation)
        inci_indicators = [
            # Water-based
            'Glycerin', 'Propanediol', 'Squalane', 'Tocopherol', 'Phenoxyethanol',
            'Dimethicone', 'Sodium Hyaluronate', 'Niacinamide', 'Polyglyceryl',
            # Oils and waxes (for lipsticks, etc)
            'Ricinus', 'Castor', 'Jojoba', 'Cera Alba', 'Beeswax', 'Candelilla',
            'Carnauba', 'Lanolin', 'Caprylic', 'Isopropyl', 'Cetearyl',
            # Color cosmetics
            'Mica', 'Titanium Dioxide', 'Iron Oxide', 'CI 77', 'Silica',
            'Kaolin', 'Talc', 'Zinc Oxide', 'Bismuth',
            # Butters
            'Butyrospermum', 'Shea', 'Cocoa', 'Mango',
        ]

        best_match = None
        best_score = 0

        # Method 1: Look for "Ingredients" label followed by list
        ing_patterns = [
            r'[Ii]ngredients?\s*[:\-]?\s*</[^>]+>\s*<[^>]+>([^<]+(?:<br[^>]*>[^<]+)*)',
            r'metafield-rich_text_field[^>]*>\s*<p>([^<]+)',
            r'ingredients-accordion[^>]*>.*?<p>([^<]+)',
        ]

        for pattern in ing_patterns:
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                text = match.group(1)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) > 20:
                    indicator_count = sum(1 for ind in inci_indicators if ind.lower() in text.lower())
                    if indicator_count >= 1:
                        score = indicator_count + (len(text) / 100)
                        if score > best_score:
                            best_match = text
                            best_score = score

        # Method 2: Look for Water/Aqua start (water-based products)
        for match in re.finditer(r'(?:Water|Aqua|Eau)(?:/(?:Water|Aqua|Eau))*', html, re.IGNORECASE):
            start = match.start()
            context = html[start:start+5000]

            indicator_count = sum(1 for ind in inci_indicators if ind.lower() in context.lower())
            comma_count = context.count(',')

            if comma_count >= 3 and indicator_count >= 1:
                inci_match = re.match(r'([A-Za-z0-9\s,\(\)\-\/\.\*\[\]\+\:\'\"\&\;\_\#]+)', context)
                if inci_match:
                    ingredients = inci_match.group(1)
                    ingredients = re.sub(r'\s+', ' ', ingredients).strip()
                    ingredients = re.sub(r'[\.\s]+$', '', ingredients)
                    ingredients = re.sub(r'&[a-z]+;', '', ingredients)
                    ingredients = re.sub(r'&#\d+;', "'", ingredients)

                    score = indicator_count + (len(ingredients) / 100)
                    if score > best_score and len(ingredients) > 50:
                        best_match = ingredients
                        best_score = score

        # Method 3: Look for oil/wax-based starts (lipsticks, balms)
        oil_starts = [
            r'(?:Ricinus Communis|Castor)[^,]*(?:Seed)?\s*Oil',
            r'(?:Cera Alba|Beeswax)',
            r'(?:Hydrogenated\s+)?(?:Polyisobutene|Polybutene)',
            r'Diisostearyl Malate',
            r'Octyldodecanol',
            r'(?:Mica|Talc|Silica)',
        ]

        for oil_pattern in oil_starts:
            for match in re.finditer(oil_pattern, html, re.IGNORECASE):
                start = match.start()
                context = html[start:start+3000]

                indicator_count = sum(1 for ind in inci_indicators if ind.lower() in context.lower())
                comma_count = context.count(',')

                if comma_count >= 2 and indicator_count >= 1:
                    inci_match = re.match(r'([A-Za-z0-9\s,\(\)\-\/\.\*\[\]\+\:\'\"\&\;\_\#]+)', context)
                    if inci_match:
                        ingredients = inci_match.group(1)
                        ingredients = re.sub(r'\s+', ' ', ingredients).strip()
                        ingredients = re.sub(r'[\.\s]+$', '', ingredients)
                        ingredients = re.sub(r'&[a-z]+;', '', ingredients)
                        ingredients = re.sub(r'&#\d+;', "'", ingredients)

                        score = indicator_count + (len(ingredients) / 100)
                        if score > best_score and len(ingredients) > 30:
                            best_match = ingredients
                            best_score = score

        if best_match:
            return best_match[:5000]

        return None

    except Exception as e:
        return None


def scrape_credo_product(handle: str) -> Optional[Dict]:
    """
    Fetch product data from Credo Beauty by handle.
    Returns price and Credo URL for affiliate linking.
    """
    credo_url = f"https://credobeauty.com/products/{handle}"
    json_url = f"{credo_url}.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json",
    }

    try:
        resp = requests.get(json_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        product = data.get("product", {})

        return {
            "credo_url": credo_url,
            "credo_price": float(product.get("variants", [{}])[0].get("price", 0)) if product.get("variants") else 0,
            "credo_title": product.get("title", ""),
            "credo_handle": product.get("handle", ""),
        }
    except Exception as e:
        print(f"  Credo lookup failed for {handle}: {e}")
        return None


def scrape_sephora_product(product_name: str, brand: str = "") -> Optional[Dict]:
    """
    Search Sephora for a product by name and brand via HTML scraping.
    Returns Sephora URL and additional product data if found.
    """
    import urllib.parse
    import re

    # Build search query
    query = f"{brand} {product_name}".strip()
    encoded_query = urllib.parse.quote(query)

    search_url = f"https://www.sephora.com/search?keyword={encoded_query}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get(search_url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text

        # Look for product links in search results
        # Pattern: href="/product/brand-name-product-name-P123456"
        product_pattern = r'href="(/product/[^"]+)"'
        matches = re.findall(product_pattern, html)

        if not matches:
            return None

        # Get first matching product
        product_path = matches[0]
        product_url = f"https://www.sephora.com{product_path}"

        # Try to extract rating from the HTML
        rating = 0
        rating_match = re.search(r'"rating":(\d+\.?\d*)', html)
        if rating_match:
            rating = float(rating_match.group(1))

        # Try to extract review count
        reviews = 0
        reviews_match = re.search(r'"reviewCount":(\d+)', html)
        if reviews_match:
            reviews = int(reviews_match.group(1))

        return {
            "sephora_url": product_url,
            "sephora_price": 0,  # Would need to scrape product page
            "sephora_title": "",
            "sephora_brand": brand,
            "sephora_rating": rating,
            "sephora_reviews": reviews,
        }
    except Exception as e:
        # Silently fail - Sephora is optional
        return None


def scrape_shopify_product(url: str) -> Optional[Dict]:
    """Scrape single Shopify product page via JSON API."""
    json_url = url.rstrip("/") + ".json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json",
    }

    try:
        resp = requests.get(json_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        product = data.get("product", {})

        return {
            "url": url,
            "title": product.get("title", ""),
            "handle": product.get("handle", ""),
            "vendor": product.get("vendor", ""),
            "product_type": product.get("product_type", ""),
            "tags": product.get("tags", []),
            "body_html": product.get("body_html", ""),
            "price": float(product.get("variants", [{}])[0].get("price", 0)) if product.get("variants") else 0,
            "main_image": product.get("images", [{}])[0].get("src", "") if product.get("images") else "",
            "images": [img.get("src", "") for img in product.get("images", [])[:10]],
        }
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None


def scrape_shopify_collection(collection_url: str, limit: int = None) -> List[Dict]:
    """Scrape entire Shopify collection via JSON API."""
    domain = urlparse(collection_url).netloc
    products = []
    page = 1

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json",
    }

    print(f"  Fetching products from {domain}...")

    while True:
        url = f"https://{domain}/products.json?limit=250&page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            break

        page_products = data.get("products", [])
        if not page_products:
            break

        for p in page_products:
            products.append({
                "url": f"https://{domain}/products/{p.get('handle', '')}",
                "title": p.get("title", ""),
                "handle": p.get("handle", ""),
                "vendor": p.get("vendor", ""),
                "product_type": p.get("product_type", ""),
                "tags": p.get("tags", []),
                "body_html": p.get("body_html", ""),
                "price": float(p.get("variants", [{}])[0].get("price", 0)) if p.get("variants") else 0,
                "main_image": p.get("images", [{}])[0].get("src", "") if p.get("images") else "",
                "images": [img.get("src", "") for img in p.get("images", [])[:10]],
            })

            if limit and len(products) >= limit:
                return products

        print(f"  Page {page}: {len(page_products)} products (total: {len(products)})")
        page += 1
        time.sleep(0.5)

    return products


def scrape_generic_product(url: str) -> Optional[Dict]:
    """Scrape non-Shopify product page via HTML parsing."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "text/html",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove non-content
    for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer"]):
        tag.decompose()

    # Extract data
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)

    brand = ""
    meta_brand = soup.find("meta", {"property": "og:site_name"})
    if meta_brand:
        brand = meta_brand.get("content", "")

    main_image = ""
    og_img = soup.find("meta", {"property": "og:image"})
    if og_img:
        main_image = og_img.get("content", "")

    return {
        "url": url,
        "title": title,
        "handle": urlparse(url).path.split("/")[-1],
        "vendor": brand,
        "product_type": "",
        "tags": [],
        "body_html": soup.get_text(separator=" ", strip=True)[:10000],
        "price": 0,
        "main_image": main_image,
        "images": [main_image] if main_image else [],
    }


# =============================================================================
# CLASSIFICATION
# =============================================================================

def process_product(product_data: Dict, use_ai: bool = False) -> Dict:
    """
    Process scraped product through classifier.
    Returns classified product ready for Webflow.
    """
    # Build text for classification
    body_text = ""
    if product_data.get("body_html"):
        soup = BeautifulSoup(product_data["body_html"], "html.parser")
        body_text = soup.get_text(separator=" ", strip=True)

    full_text = " ".join([
        product_data.get("title", ""),
        product_data.get("vendor", ""),
        product_data.get("product_type", ""),
        " ".join(product_data.get("tags", [])) if isinstance(product_data.get("tags"), list) else "",
        body_text,
    ])

    # Classify with local regex (FREE)
    classified = classify_product(
        text=full_text,
        product_name=product_data.get("title", ""),
        brand=product_data.get("vendor", ""),
    )

    # Add scraped data
    classified["brand_url"] = product_data.get("url", "")  # Original brand URL
    classified["main_image"] = product_data.get("main_image", "")
    classified["images"] = product_data.get("images", [])
    classified["video_url"] = product_data.get("video_url", "")  # Video URL if available

    # Look up Credo data for price and affiliate URL
    handle = product_data.get("handle", "")
    credo_data = scrape_credo_product(handle) if handle else None

    if credo_data:
        classified["credo_url"] = credo_data["credo_url"]
        classified["price"] = credo_data["credo_price"]  # Use Credo price
        print(f"  Credo: ${credo_data['credo_price']} at {credo_data['credo_url']}")
    else:
        # Fallback to brand price if Credo lookup fails
        classified["credo_url"] = ""
        classified["price"] = product_data.get("price", 0)
        print(f"  No Credo listing found, using brand price: ${classified['price']}")

    # Look up Sephora data for ratings, reviews, and alternate pricing
    product_name = product_data.get("title", "")
    brand = product_data.get("vendor", "")
    sephora_data = scrape_sephora_product(product_name, brand) if product_name else None

    if sephora_data:
        classified["sephora_url"] = sephora_data["sephora_url"]
        classified["sephora_rating"] = sephora_data.get("sephora_rating", 0)
        classified["sephora_reviews"] = sephora_data.get("sephora_reviews", 0)
        # Use Sephora price if no Credo price
        if not classified.get("price") or classified["price"] == 0:
            classified["price"] = sephora_data["sephora_price"]
        print(f"  Sephora: {sephora_data['sephora_rating']}★ ({sephora_data['sephora_reviews']} reviews)")
    else:
        classified["sephora_url"] = ""

    # Extract full INCI ingredient list from product page
    url = product_data.get("url", "")
    if url:
        ingredients = extract_full_ingredients(url)
        if ingredients:
            classified["ingredients"] = ingredients

    # Add base content from scraped data (FREE)
    classified["what_it_is"] = body_text[:3000] if body_text else ""
    classified["whats_it_in"] = product_data.get("product_type", "")

    # Enhance with AI to generate polished 5 dropdown fields
    if use_ai:
        classified = enhance_with_ai(classified, body_text)

    return classified


def enhance_with_ai(product: Dict, text: str) -> Dict:
    """
    AI enhancement using Claude API to generate the 5 dropdown fields.
    Cost: ~$0.001 per product using Haiku.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  Skipping AI (no ANTHROPIC_API_KEY)")
        return product

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
                "max_tokens": 1500,
                "messages": [{
                    "role": "user",
                    "content": f"""Analyze this beauty product and generate content for a product card.

Product: {product.get('name', 'Unknown')}
Brand: {product.get('brand', 'Unknown')}
Detected attributes: {', '.join(product.get('detected_attributes', [])[:15])}
Product text: {text[:3000]}

Generate JSON with ALL these fields (be concise but informative):

1. "what_it_is": A clear 2-3 sentence description of what this product is and its key benefits.

2. "who_its_for": Who should use this product? Mention skin types, concerns, or lifestyles. 1-2 sentences.

3. "how_to_use": Brief application instructions. 1-2 sentences.

4. "whats_in_it": List 3-5 key hero ingredients and what they do. Format as bullet points with dashes.

5. "whats_it_in": The product format/packaging (e.g., "Glass bottle with dropper", "Recyclable tube").

6. "product_type": The specific product type (e.g., "Serum", "Moisturizer", "Foundation", "Lipstick", "Mascara", "Cleanser", "Toner", "Eye Cream", "Sunscreen", "Primer", "Concealer", "Blush", "Bronzer", "Highlighter", "Setting Powder", "Lip Balm", "Lip Gloss", "Brow Gel", "Eyeliner").

7. "category": The broader category (e.g., "Skincare", "Makeup", "Haircare", "Body Care", "Sun Care", "Tools & Accessories").

8. "formulation": The product formulation type (e.g., "Cream", "Gel", "Oil", "Serum", "Liquid", "Powder", "Balm", "Mousse", "Spray", "Stick", "Foam").

9. "finish": The finish or effect (e.g., "Matte", "Dewy", "Satin", "Natural", "Luminous", "Radiant", "Velvet", "Glossy", "Sheer"). Use "N/A" if not applicable.

10. "coverage": Coverage level for makeup (e.g., "Full", "Medium", "Light", "Sheer", "Buildable"). Use "N/A" for skincare/haircare.

11. "skin_types": Comma-separated list of suitable skin types (e.g., "All Skin Types", "Dry", "Oily", "Combination", "Sensitive", "Normal", "Mature", "Acne-Prone").

12. "instructions": Detailed usage instructions. 2-3 sentences with specific steps.

13. "packaging": Primary packaging description (e.g., "Glass bottle", "Plastic tube", "Compact", "Jar", "Pump bottle", "Dropper bottle", "Stick", "Pot").

14. "packaging_inner_outer": Both inner and outer packaging (e.g., "Glass bottle with pump, recyclable cardboard box" or "Plastic tube, no outer box").

Return valid JSON only, no markdown code blocks."""
                }]
            },
            timeout=30,
        )
        resp.raise_for_status()

        content = resp.json().get("content", [{}])[0].get("text", "{}")

        # Clean up response if wrapped in markdown
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        ai_data = json.loads(content)

        # Map AI response to product fields - Original 5 dropdown fields
        product["what_it_is"] = ai_data.get("what_it_is", product.get("what_it_is", ""))
        product["who_its_for"] = ai_data.get("who_its_for", "")
        product["how_to_use"] = ai_data.get("how_to_use", "")

        # Handle whats_in_it - combine key ingredients from AI + full INCI list
        whats_in_it = ai_data.get("whats_in_it", "")
        if isinstance(whats_in_it, list):
            whats_in_it = "\n".join(whats_in_it)

        # Combine key ingredients with full INCI list if available
        full_inci = product.get("ingredients", "")
        if full_inci:
            if whats_in_it:
                whats_in_it = f"KEY INGREDIENTS:\n{whats_in_it}\n\nFULL INGREDIENT LIST:\n{full_inci}"
            else:
                whats_in_it = f"FULL INGREDIENT LIST:\n{full_inci}"

        product["whats_in_it"] = whats_in_it
        product["whats_it_in"] = ai_data.get("whats_it_in", product.get("whats_it_in", ""))

        # Helper to convert lists to comma-separated strings
        def to_string(val):
            if isinstance(val, list):
                return ", ".join(str(v) for v in val)
            return str(val) if val else ""

        # New classification fields - ensure all are strings (not arrays)
        product["product_type"] = to_string(ai_data.get("product_type", ""))
        product["category"] = to_string(ai_data.get("category", ""))
        product["formulation"] = to_string(ai_data.get("formulation", ""))
        product["finish"] = to_string(ai_data.get("finish", ""))
        product["coverage"] = to_string(ai_data.get("coverage", ""))
        product["skin_types"] = to_string(ai_data.get("skin_types", ""))
        product["instructions"] = to_string(ai_data.get("instructions", ""))
        product["packaging"] = to_string(ai_data.get("packaging", ""))
        product["packaging_inner_outer"] = to_string(ai_data.get("packaging_inner_outer", ""))

        product["ai_enhanced"] = True

    except Exception as e:
        print(f"  AI enhancement failed: {e}")

    return product


# =============================================================================
# WEBFLOW PUSH
# =============================================================================

def push_to_webflow(product: Dict, client: WebflowClient) -> Dict:
    """Push classified product to Webflow CMS."""
    brand_name = product.get("brand", "")
    brand_id = client.find_brand_id(brand_name) if brand_name else None

    if not brand_id:
        print(f"  Warning: Brand '{brand_name}' not found in Webflow")
        product["webflow_status"] = f"skipped: brand '{brand_name}' not in Webflow"
        return product

    try:
        field_data = product_to_webflow_fields(product, brand_id=brand_id)
        result = client.upsert_item(field_data)
        product["webflow_id"] = result.get("id")
        product["webflow_status"] = "pushed"
        print(f"  Pushed: {result.get('id')}")
    except Exception as e:
        product["webflow_status"] = f"error: {e}"
        print(f"  Error: {e}")

    return product


# =============================================================================
# GOOGLE SHEETS INTEGRATION (Optional)
# =============================================================================

def process_sheets_queue(push: bool = False, client: WebflowClient = None) -> Dict:
    """Process one pending product from Google Sheets queue."""
    # Try to import sheets module from automation folder
    automation_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "automation"
    )
    sys.path.insert(0, automation_path)

    try:
        from sheets import get_pending_product, mark_product_complete, mark_product_error
    except ImportError:
        print("Error: Google Sheets integration not available")
        print("Make sure automation/sheets.py exists and GOOGLE_CREDENTIALS_JSON is set")
        return {"error": "sheets module not found"}

    # Get pending product
    pending = get_pending_product()
    if not pending:
        print("No pending products in queue")
        return {"status": "empty"}

    print(f"Processing: {pending['url']}")

    # Scrape product
    product_data = scrape_shopify_product(pending["url"])
    if not product_data:
        product_data = scrape_generic_product(pending["url"])

    if not product_data:
        mark_product_error(pending["row_number"], "Failed to scrape")
        return {"error": "scrape failed", "url": pending["url"]}

    # Process
    classified = process_product(product_data)

    # Push to Webflow
    if push and client:
        classified = push_to_webflow(classified, client)
        if classified.get("webflow_status") == "pushed":
            mark_product_complete(pending["row_number"])
        else:
            mark_product_error(pending["row_number"], classified.get("webflow_status", "unknown error"))

    return classified


# =============================================================================
# MAIN CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified iHeartClean Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single product
  python unified_pipeline.py "https://kosas.com/products/revealer" --push

  # Entire brand catalog
  python unified_pipeline.py "https://kosas.com/collections/all" --brand --push --limit 10

  # Process Google Sheets queue
  python unified_pipeline.py --sheets --push

  # With AI enhancement
  python unified_pipeline.py "https://..." --push --ai
        """
    )

    parser.add_argument("url", nargs="?", help="Product or collection URL")
    parser.add_argument("--brand", action="store_true", help="Treat URL as brand collection")
    parser.add_argument("--sheets", action="store_true", help="Process from Google Sheets queue")
    parser.add_argument("--push", action="store_true", help="Push to Webflow CMS")
    parser.add_argument("--ai", action="store_true", help="Enable AI enhancement (~$0.001/product)")
    parser.add_argument("--limit", type=int, help="Limit products for brand scraping")
    parser.add_argument("--output", "-o", help="Output JSON file")

    args = parser.parse_args()

    # Setup Webflow client
    client = None
    if args.push:
        config = WebflowConfig.from_env()
        if not config.api_token:
            print("Error: WEBFLOW_API_TOKEN not set")
            sys.exit(1)
        client = WebflowClient(config)
        print("Webflow client initialized")

    results = {"products": [], "failed": []}

    # Process based on mode
    if args.sheets:
        # Google Sheets mode
        result = process_sheets_queue(args.push, client)
        if "error" in result:
            results["failed"].append(result)
        else:
            results["products"].append(result)

    elif args.url:
        url_type = detect_url_type(args.url)

        if args.brand or url_type == "collection":
            # Brand/collection mode
            print(f"\n{'#'*60}")
            print(f"BRAND SCRAPER: {args.url}")
            print(f"{'#'*60}\n")

            products = scrape_shopify_collection(args.url, args.limit)
            print(f"\nProcessing {len(products)} products...\n")

            for i, product_data in enumerate(products, 1):
                print(f"[{i}/{len(products)}] {product_data['title'][:50]}...")

                try:
                    classified = process_product(product_data, args.ai)
                    print(f"  Score: {classified['overall_score']}/5, Attrs: {classified['attribute_count']}")

                    if args.push and client:
                        classified = push_to_webflow(classified, client)

                    results["products"].append(classified)
                except Exception as e:
                    print(f"  Failed: {e}")
                    results["failed"].append({"url": product_data["url"], "error": str(e)})

                time.sleep(0.5)

        else:
            # Single product mode
            print(f"\nProcessing: {args.url}")

            product_data = scrape_shopify_product(args.url)
            if not product_data:
                product_data = scrape_generic_product(args.url)

            if product_data:
                classified = process_product(product_data, args.ai)
                print(f"Score: {classified['overall_score']}/5")
                print(f"Attributes: {classified['attribute_count']}")
                print(f"Detected: {', '.join(classified['detected_attributes'][:10])}")

                if args.push and client:
                    classified = push_to_webflow(classified, client)

                results["products"].append(classified)
            else:
                results["failed"].append({"url": args.url, "error": "scrape failed"})

    else:
        parser.print_help()
        sys.exit(1)

    # Summary
    print(f"\n{'='*60}")
    print(f"COMPLETE: {len(results['products'])} succeeded, {len(results['failed'])} failed")
    print(f"{'='*60}")

    # Output
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {args.output}")
    elif len(results["products"]) <= 3:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
