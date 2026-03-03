#!/usr/bin/env python3
"""
Scrape a brand from Credo Beauty and push to Webflow.
Uses AI to generate drawer content and classify attributes.

Usage:
    python scrape_credo_brand.py gen-see
    python scrape_credo_brand.py westman-atelier --limit 5
"""

import os
import sys
import re
import time
import json
import argparse
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

from classifier import classify_product
from webflow_client import WebflowClient, WebflowConfig, product_to_webflow_fields
from icon_mapping import map_attributes_to_icons, format_for_webflow
from persona_scorer import calculate_persona_scores

CREDO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/html",
}


def fetch_credo_products(brand_handle, limit=None):
    """Fetch all products for a brand from Credo Beauty."""
    products = []
    page = 1

    while True:
        url = f"https://credobeauty.com/collections/{brand_handle}/products.json?limit=250&page={page}"
        resp = requests.get(url, headers=CREDO_HEADERS, timeout=15)

        if resp.status_code != 200:
            print(f"   Error fetching page {page}: HTTP {resp.status_code}")
            break

        data = resp.json()
        page_products = data.get("products", [])

        if not page_products:
            break

        products.extend(page_products)
        print(f"   Fetched page {page}: {len(page_products)} products (total: {len(products)})")

        if limit and len(products) >= limit:
            products = products[:limit]
            break

        if len(page_products) < 250:
            break

        page += 1
        time.sleep(0.3)

    return products


def fetch_product_page(handle):
    """Fetch full product page HTML for additional details."""
    url = f"https://credobeauty.com/products/{handle}"
    try:
        resp = requests.get(url, headers=CREDO_HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.text
    except:
        pass
    return ""


def extract_ingredients(html):
    """Extract ingredients from product page HTML."""
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    # Look for ingredients section
    patterns = [
        r"(?:full\s+)?ingredients?[:\s]+([A-Za-z][\w\s,\(\)\-\*\.]+?)(?:\.|$|how to|directions)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            ingredients = match.group(1).strip()
            if len(ingredients) > 50:  # Valid ingredients list
                return ingredients[:2000]

    return ""


def ai_enhance_product(product_data):
    """Use Claude to analyze product and generate drawer content."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("      No ANTHROPIC_API_KEY - skipping AI enhancement")
        return {}

    name = product_data.get("title", "")
    brand = product_data.get("vendor", "")
    description = product_data.get("body_text", "")
    tags = product_data.get("tags", [])
    if isinstance(tags, list):
        tags = ", ".join(tags)
    price = product_data.get("price", "")
    product_type = product_data.get("product_type", "")

    prompt = f"""Analyze this clean beauty product and provide structured information for a product card.

PRODUCT: {name}
BRAND: {brand}
PRICE: ${price}
TYPE: {product_type}
TAGS: {tags}
DESCRIPTION: {description}

Respond in this exact JSON format (no markdown, just valid JSON):
{{
  "what_it_is": "2-3 sentences describing what this product is, its key benefits, and what makes it special",
  "who_its_for": "Who should use this product - skin types, concerns, lifestyles, age groups",
  "how_to_use": "Clear application instructions in 2-3 sentences",
  "whats_in_it": "Key hero ingredients and their benefits (e.g., 'Vitamin C for brightening, Hyaluronic Acid for hydration')",
  "whats_it_in": "Product format and packaging description (e.g., 'Recyclable glass jar with pump dispenser')",
  "product_type": "Specific product type like 'Mascara', 'Lip Gloss', 'Brow Pomade', 'Blush', 'Highlighter'",
  "category": "Broader category: 'Makeup', 'Skincare', 'Body Care', 'Hair Care', or 'Tools'",
  "formulation": "Product texture: 'Cream', 'Gel', 'Oil', 'Powder', 'Liquid', 'Balm', 'Mousse', 'Wax'",
  "skin_types": "Suitable skin types: 'All skin types', 'Dry', 'Oily', 'Sensitive', 'Combination'",
  "detected_claims": ["list", "of", "beauty", "attributes", "like", "vegan", "cruelty-free", "clean", "fragrance-free", "paraben-free", "buildable", "long-wearing", "hydrating", "nourishing"]
}}

Focus on clean beauty values. Be specific and accurate based on the product info provided."""

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
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        resp.raise_for_status()

        content = resp.json()["content"][0]["text"]
        # Parse JSON from response
        enhanced = json.loads(content)
        return enhanced

    except json.JSONDecodeError as e:
        print(f"      AI JSON parse error: {e}")
        return {}
    except Exception as e:
        print(f"      AI enhancement error: {e}")
        return {}


def process_credo_product(credo_product, brand_handle):
    """Process a single Credo product into Webflow format."""
    # Extract basic info
    handle = credo_product.get("handle", "")
    title = credo_product.get("title", "")
    vendor = credo_product.get("vendor", "")
    product_type = credo_product.get("product_type", "")
    tags = credo_product.get("tags", [])
    body_html = credo_product.get("body_html", "")
    images = [img.get("src", "") for img in credo_product.get("images", [])]
    variants = credo_product.get("variants", [])

    # Get price
    price = 0
    if variants:
        try:
            price = float(variants[0].get("price", 0))
        except:
            price = 0

    # Clean body HTML
    body_text = ""
    if body_html:
        soup = BeautifulSoup(body_html, "html.parser")
        body_text = soup.get_text(separator=" ", strip=True)

    # Fetch full product page for ingredients
    print(f"      Fetching product page for ingredients...")
    html = fetch_product_page(handle)
    ingredients = extract_ingredients(html)

    # Build text for classification
    full_text = " ".join([
        title,
        vendor,
        product_type,
        " ".join(tags) if isinstance(tags, list) else tags,
        body_text,
    ])

    # Classify product
    classified = classify_product(
        text=full_text,
        product_name=title,
        brand=vendor,
    )

    # AI Enhancement
    print(f"      Generating AI content...")
    ai_data = ai_enhance_product({
        "title": title,
        "vendor": vendor,
        "body_text": body_text,
        "tags": tags,
        "price": price,
        "product_type": product_type,
    })

    # Build product dict
    product = {
        "name": title,
        "slug": f"{brand_handle}-{handle}",
        "brand": vendor,
        "price": price,
        "url": f"https://credobeauty.com/products/{handle}",
        "credo_url": f"https://credobeauty.com/products/{handle}",
        "main_image": images[0] if images else "",
        "images": images[:10],
        "ingredients": ingredients,
        "detected_attributes": classified.get("detected_attributes", []),
        "overall_score": classified.get("overall_score", 0),

        # AI-generated content
        "what_it_is": ai_data.get("what_it_is", ""),
        "who_its_for": ai_data.get("who_its_for", ""),
        "how_to_use": ai_data.get("how_to_use", ""),
        "whats_in_it": ai_data.get("whats_in_it", ""),
        "whats_it_in": ai_data.get("whats_it_in", ""),
        "product_type": ai_data.get("product_type", product_type),
        "category": ai_data.get("category", "Makeup"),
        "formulation": ai_data.get("formulation", ""),
        "skin_types": ai_data.get("skin_types", "All skin types"),
    }

    # Merge AI-detected claims with regex-detected attributes
    ai_claims = ai_data.get("detected_claims", [])
    if ai_claims:
        normalized = [c.lower().replace("-", "_").replace(" ", "_") for c in ai_claims]
        existing = product.get("detected_attributes", [])
        merged = list(set(existing + normalized))
        product["detected_attributes"] = merged

    # Add formulation to detected_attributes for icon mapping
    formulation = ai_data.get("formulation", "").lower().strip()
    if formulation:
        formulation_normalized = formulation.replace(" ", "_").replace("-", "_")
        if formulation_normalized not in product["detected_attributes"]:
            product["detected_attributes"].append(formulation_normalized)

    # Add skin types as attributes
    skin_types = ai_data.get("skin_types", "").lower()
    if skin_types:
        if "all skin" in skin_types or "all types" in skin_types:
            product["detected_attributes"].append("all_skin_types")
        if "sensitive" in skin_types:
            product["detected_attributes"].append("sensitive_skin")
        if "oily" in skin_types:
            product["detected_attributes"].append("oily_skin")
        if "dry" in skin_types:
            product["detected_attributes"].append("dry_skin")
        if "combination" in skin_types:
            product["detected_attributes"].append("combination_skin")

    return product


def get_brand_logo(brand_handle):
    """Get brand logo URL from Credo."""
    try:
        # Try to get logo from Credo's brand page
        url = f"https://credobeauty.com/collections/{brand_handle}"
        resp = requests.get(url, headers=CREDO_HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Look for brand logo in the page
            og_img = soup.find("meta", {"property": "og:image"})
            if og_img and og_img.get("content"):
                return og_img["content"]
    except:
        pass

    # Use first product image as fallback
    try:
        url = f"https://credobeauty.com/collections/{brand_handle}/products.json?limit=1"
        resp = requests.get(url, headers=CREDO_HEADERS, timeout=10)
        if resp.status_code == 200:
            products = resp.json().get("products", [])
            if products and products[0].get("images"):
                return products[0]["images"][0].get("src", "")
    except:
        pass

    return ""


def create_brand_if_needed(client, brand_name, brand_handle):
    """Create brand in Webflow if it doesn't exist, return brand ID."""
    brand_id = client.find_brand_id(brand_name)
    if brand_id:
        print(f"   Found existing brand: {brand_name} ({brand_id})")
        return brand_id

    # Create new brand
    print(f"   Creating new brand: {brand_name}")
    slug = brand_name.lower().replace(" ", "-")

    # Get brand logo
    logo_url = get_brand_logo(brand_handle)
    print(f"   Logo URL: {logo_url[:60] if logo_url else 'None'}...")

    brand_data = {
        "name": brand_name,
        "slug": slug,
    }

    if logo_url:
        brand_data["logo"] = {"url": logo_url}

    try:
        result = client.create_item(
            brand_data,
            collection_id=client.BRANDS_COLLECTION_ID
        )
        brand_id = result.get("id")
        print(f"   Created brand: {brand_name} ({brand_id})")
        # Update cache
        client._brand_cache[slug] = brand_id
        return brand_id
    except Exception as e:
        print(f"   Error creating brand: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Scrape brand from Credo Beauty")
    parser.add_argument("brand_handle", help="Credo brand handle (e.g., 'gen-see', 'westman-atelier')")
    parser.add_argument("--limit", type=int, help="Limit number of products")
    parser.add_argument("--dry-run", action="store_true", help="Don't push to Webflow")

    args = parser.parse_args()

    print("=" * 70)
    print(f"SCRAPE CREDO BRAND: {args.brand_handle}")
    print("=" * 70)

    # Initialize Webflow client
    config = WebflowConfig.from_env()
    if not config.api_token:
        print("Error: WEBFLOW_API_TOKEN not set")
        sys.exit(1)

    client = WebflowClient(config)

    # Fetch products from Credo
    print(f"\n1. Fetching products from Credo Beauty...")
    credo_products = fetch_credo_products(args.brand_handle, args.limit)
    print(f"   Found {len(credo_products)} products")

    if not credo_products:
        print("   No products found. Check if brand handle is correct.")
        sys.exit(1)

    # Get brand name from first product
    brand_name = credo_products[0].get("vendor", args.brand_handle.replace("-", " ").title())

    # Create or find brand
    print(f"\n2. Setting up brand: {brand_name}")
    brand_id = create_brand_if_needed(client, brand_name, args.brand_handle)

    if not brand_id:
        print("   Error: Could not find or create brand")
        sys.exit(1)

    # Process products
    print(f"\n3. Processing {len(credo_products)} products...")

    results = {"success": [], "failed": []}

    for i, credo_product in enumerate(credo_products, 1):
        title = credo_product.get("title", "Unknown")
        print(f"\n   [{i}/{len(credo_products)}] {title}")

        try:
            # Process product
            product = process_credo_product(credo_product, args.brand_handle)

            # Calculate persona scores - map to webflow field names expected by scorer
            print(f"      Calculating persona scores...")
            scorer_input = {
                "name": product.get("name", ""),
                "brand-name-2": product.get("brand", ""),
                "what-it-is-2": product.get("what_it_is", ""),
                "who-it-s-for-5": product.get("who_its_for", ""),
                "how-to-use-it-7": product.get("how_to_use", ""),
                "what-s-in-it": product.get("whats_in_it", ""),
                "ingredients-2": product.get("ingredients", ""),
            }
            scores = calculate_persona_scores(scorer_input)
            product.update(scores)

            # Convert to Webflow fields
            fields = product_to_webflow_fields(product, brand_id=brand_id)

            if args.dry_run:
                print(f"      [DRY RUN] Would push: {product['name']}")
                print(f"      Score: {product.get('overall_score', 0)}/5, Attrs: {len(product.get('detected_attributes', []))}")
                results["success"].append({"name": title, "status": "dry_run"})
            else:
                # Push to Webflow
                print(f"      Pushing to Webflow...")
                result = client.upsert_item(fields)
                print(f"      ✓ Created: {result.get('id')}")
                results["success"].append({"name": title, "id": result.get("id")})

            # Rate limiting
            time.sleep(0.5)

        except Exception as e:
            print(f"      ✗ Error: {e}")
            results["failed"].append({"name": title, "error": str(e)})

    # Summary
    print(f"\n{'=' * 70}")
    print("COMPLETE")
    print("=" * 70)
    print(f"  Brand: {brand_name}")
    print(f"  Success: {len(results['success'])}")
    print(f"  Failed: {len(results['failed'])}")

    if results["failed"]:
        print("\n  Failed products:")
        for f in results["failed"]:
            print(f"    - {f['name']}: {f['error'][:50]}")


if __name__ == "__main__":
    main()
