#!/usr/bin/env python3
"""
Sync products with Credo Beauty website.
- Checks if each product exists on Credo Beauty
- Updates product-url field with Credo Beauty link
- Archives products not found on Credo Beauty
"""

import os
import re
import sys
import time
import json
import requests
from urllib.parse import quote, urljoin
from dotenv import load_dotenv

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

api_token = os.environ.get("WEBFLOW_API_TOKEN")
collection_id = os.environ.get("WEBFLOW_COLLECTION_ID")

headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json",
    "accept": "application/json",
}

# Request headers for Credo Beauty
CREDO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html",
}

# Brands NOT on Credo Beauty - archive all products from these brands
BRANDS_NOT_ON_CREDO = {
    "rare beauty",
    "milk makeup",
    "merit beauty",
    "merit",
    "rhode",
}

# Brand name mappings (our name -> Credo's brand handle)
BRAND_MAPPINGS = {
    "westman-atelier": "westman-atelier",
    "westman atelier": "westman-atelier",
    "soshe beauty": "soshe-beauty",
    "soshe": "soshe-beauty",
    "gen see": "gen-see",
    "gensee": "gen-see",
    "marie veronique": "marie-veronique",
    "marie-veronique": "marie-veronique",
    "tata harper skincare": "tata-harper",
    "tata harper": "tata-harper",
    "kosas cosmetics": "kosas",
    "kosas": "kosas",
    "rms beauty": "rms-beauty",
    "ilia beauty": "ilia",
    "ilia beauty v2": "ilia",
    "ilia": "ilia",
    "tower 28 beauty": "tower-28",
    "tower 28": "tower-28",
    "indie lee": "indie-lee",
    "ursa_major": "ursa-major",
    "ursa major": "ursa-major",
    "mob beauty": "mob-beauty",
    "true botanicals": "true-botanicals",
    "lys beauty": "lys-beauty",
    "nécessaire": "necessaire",
    "necessaire": "necessaire",
    "nécessaire, a personal care company": "necessaire",
    "exa": "exa",
    "finding ferdinand": "finding-ferdinand",
    "osea malibu": "osea",
    "osea® malibu": "osea",
    "osea": "osea",
    "grown alchemist": "grown-alchemist",
    "jillian dempsey": "jillian-dempsey",
}

# Products to skip (gift cards, test items, etc.)
SKIP_PATTERNS = [
    r"gift\s*card",
    r"test\s*(item|bundle|product)",
    r"free\s*sample",
    r"thank you card",
    r"education card",
    r"notecard",
    r"sample card",
]


def should_skip_product(name):
    """Check if product should be skipped (gift cards, test items, etc.)."""
    name_lower = name.lower()
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, name_lower):
            return True
    return False


def normalize_brand(brand):
    """Normalize brand name to Credo's format."""
    brand_lower = brand.lower().strip()
    return BRAND_MAPPINGS.get(brand_lower, brand_lower.replace(" ", "-").replace("_", "-"))


def is_brand_on_credo(brand):
    """Check if brand is sold on Credo Beauty."""
    brand_lower = brand.lower().strip()
    # Check if in the not-on-credo list
    for not_on in BRANDS_NOT_ON_CREDO:
        if not_on in brand_lower or brand_lower in not_on:
            return False
    return True


def create_product_handle(name, brand=None):
    """Create a Shopify-style product handle from product name."""
    # Remove brand from name if it's at the beginning
    if brand:
        brand_lower = brand.lower()
        name_lower = name.lower()
        for variant in [brand_lower, brand_lower.replace("-", " "), brand_lower.replace("-", "")]:
            if name_lower.startswith(variant):
                name = name[len(variant):].strip()
                break

    # Create handle: lowercase, replace spaces/special chars with hyphens
    handle = name.lower()
    handle = re.sub(r'[^\w\s-]', '', handle)  # Remove special chars except hyphens
    handle = re.sub(r'[\s_]+', '-', handle)   # Replace spaces/underscores with hyphens
    handle = re.sub(r'-+', '-', handle)       # Replace multiple hyphens with single
    handle = handle.strip('-')
    return handle


def fetch_credo_brand_products(brand, timeout=15):
    """
    Get all products for a brand from Credo Beauty.
    Returns dict mapping product handles to URLs.
    """
    brand_handle = normalize_brand(brand)
    products = {}
    page = 1

    while True:
        try:
            url = f"https://credobeauty.com/collections/{brand_handle}/products.json?limit=250&page={page}"
            resp = requests.get(url, headers=CREDO_HEADERS, timeout=timeout)

            if resp.status_code != 200:
                break

            data = resp.json()
            page_products = data.get("products", [])

            if not page_products:
                break

            for p in page_products:
                handle = p.get("handle", "")
                title = p.get("title", "")
                if handle:
                    # Store both the handle and normalized title for matching
                    products[handle] = {
                        "url": f"https://credobeauty.com/products/{handle}",
                        "title": title,
                        "handle": handle,
                        "title_normalized": re.sub(r'[^\w\s]', '', title.lower()),
                    }

            if len(page_products) < 250:
                break

            page += 1
            time.sleep(0.3)

        except Exception as e:
            break

    return products


def find_product_on_credo(product_name, brand, credo_products):
    """
    Find a product in the Credo catalog using fuzzy matching.
    Returns (found, url) tuple.
    """
    if not credo_products:
        return False, None

    # Normalize product name
    name_lower = product_name.lower().strip()
    brand_lower = brand.lower().replace("-", " ").replace("_", " ")

    # Remove brand prefix from product name
    clean_name = name_lower
    for variant in [brand_lower, brand_lower.replace(" ", ""), brand.lower()]:
        if clean_name.startswith(variant):
            clean_name = clean_name[len(variant):].strip()
            break

    # Also remove trailing size info like "- 30ml"
    clean_name = re.sub(r'\s*[-–]\s*\d+\s*(ml|oz|g).*$', '', clean_name, flags=re.IGNORECASE)

    # Create normalized version for matching
    clean_name_normalized = re.sub(r'[^\w\s]', '', clean_name)
    name_words = set(clean_name_normalized.split())

    # Create handle from clean name
    test_handle = create_product_handle(clean_name)

    # 1. Direct handle match
    if test_handle in credo_products:
        return True, credo_products[test_handle]["url"]

    # 2. Try with brand prefix
    brand_handle = normalize_brand(brand)
    branded_handle = f"{brand_handle}-{test_handle}"
    if branded_handle in credo_products:
        return True, credo_products[branded_handle]["url"]

    # 3. Fuzzy match by title
    best_match = None
    best_score = 0

    for handle, data in credo_products.items():
        credo_title = data["title"].lower()
        credo_normalized = data["title_normalized"]
        credo_words = set(credo_normalized.split())

        # Exact title match
        if clean_name in credo_title or credo_title in clean_name:
            return True, data["url"]

        # Word overlap scoring
        if len(name_words) >= 2 and len(credo_words) >= 2:
            overlap = name_words & credo_words
            score = len(overlap) / max(len(name_words), len(credo_words))

            if score > best_score and score >= 0.5:
                best_score = score
                best_match = data

    if best_match and best_score >= 0.6:
        return True, best_match["url"]

    return False, None


def main():
    print("=" * 70)
    print("CREDO BEAUTY SYNC")
    print("=" * 70)

    # Fetch all products from Webflow
    print("\n1. Fetching products from Webflow...")
    all_items = []
    offset = 0
    while True:
        resp = requests.get(
            f"https://api.webflow.com/v2/collections/{collection_id}/items?limit=100&offset={offset}",
            headers=headers
        )
        batch = resp.json().get("items", [])
        if not batch:
            break
        all_items.extend(batch)
        offset += 100
        if len(batch) < 100:
            break

    print(f"   Found {len(all_items)} products")

    # Group products by brand
    by_brand = {}
    for item in all_items:
        fd = item.get("fieldData", {})
        brand = fd.get("brand-name-2", "Unknown")
        if brand not in by_brand:
            by_brand[brand] = []
        by_brand[brand].append(item)

    print(f"   {len(by_brand)} brands")

    # Count brands on/off Credo
    brands_on_credo = [b for b in by_brand.keys() if is_brand_on_credo(b)]
    brands_off_credo = [b for b in by_brand.keys() if not is_brand_on_credo(b)]
    print(f"   Brands on Credo: {len(brands_on_credo)}")
    print(f"   Brands NOT on Credo: {len(brands_off_credo)}")

    # Process
    print("\n2. Processing products...")

    stats = {
        "found": 0,
        "not_found": 0,
        "updated": 0,
        "archived": 0,
        "skipped": 0,
        "already_has_url": 0,
        "brand_not_on_credo": 0,
        "errors": 0,
    }

    results = {"found": [], "not_found": [], "archived_brands": [], "errors": []}

    # First, handle brands not on Credo
    print("\n   === BRANDS NOT ON CREDO (archiving all products) ===")
    for brand in sorted(brands_off_credo):
        items = by_brand[brand]
        print(f"\n   {brand}: archiving {len(items)} products")
        results["archived_brands"].append({"brand": brand, "count": len(items)})

        for item in items:
            fd = item.get("fieldData", {})
            item_id = item["id"]
            name = fd.get("name", "")

            try:
                resp = requests.patch(
                    f"https://api.webflow.com/v2/collections/{collection_id}/items/{item_id}",
                    headers=headers,
                    json={"isArchived": True}
                )
                resp.raise_for_status()
                stats["archived"] += 1
                stats["brand_not_on_credo"] += 1
            except Exception as e:
                stats["errors"] += 1
                results["errors"].append({"name": name, "error": str(e)})

            time.sleep(0.1)

    # Now handle brands on Credo
    print("\n   === BRANDS ON CREDO ===")
    for brand in sorted(brands_on_credo):
        items = by_brand[brand]
        print(f"\n   Brand: {brand} ({len(items)} products)")

        # Fetch Credo products for this brand
        credo_products = fetch_credo_brand_products(brand)
        print(f"   Credo has {len(credo_products)} products")

        if not credo_products:
            print(f"   Warning: No products found on Credo for {brand}")

        for item in items:
            fd = item.get("fieldData", {})
            item_id = item["id"]
            name = fd.get("name", "")
            current_url = fd.get("product-url", "")

            # Skip if already has valid Credo URL
            if current_url and "credobeauty.com" in current_url:
                stats["already_has_url"] += 1
                stats["found"] += 1
                continue

            # Skip gift cards, test items, etc.
            if should_skip_product(name):
                stats["skipped"] += 1
                # Archive these items
                try:
                    resp = requests.patch(
                        f"https://api.webflow.com/v2/collections/{collection_id}/items/{item_id}",
                        headers=headers,
                        json={"isArchived": True}
                    )
                    resp.raise_for_status()
                    stats["archived"] += 1
                except:
                    pass
                time.sleep(0.1)
                continue

            # Find product on Credo
            found, credo_url = find_product_on_credo(name, brand, credo_products)

            if found and credo_url:
                stats["found"] += 1
                results["found"].append({"name": name, "brand": brand, "url": credo_url})

                # Update product-url field
                try:
                    resp = requests.patch(
                        f"https://api.webflow.com/v2/collections/{collection_id}/items/{item_id}",
                        headers=headers,
                        json={"fieldData": {"product-url": credo_url}}
                    )
                    resp.raise_for_status()
                    stats["updated"] += 1
                    print(f"      ✓ {name[:45]}")
                except Exception as e:
                    stats["errors"] += 1
                    results["errors"].append({"name": name, "error": str(e)})
            else:
                stats["not_found"] += 1
                results["not_found"].append({"name": name, "brand": brand, "id": item_id})
                print(f"      ✗ {name[:45]} - NOT FOUND")

                # Archive the product
                try:
                    resp = requests.patch(
                        f"https://api.webflow.com/v2/collections/{collection_id}/items/{item_id}",
                        headers=headers,
                        json={"isArchived": True}
                    )
                    resp.raise_for_status()
                    stats["archived"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    results["errors"].append({"name": name, "error": f"archive failed: {e}"})

            time.sleep(0.15)

    # Summary
    print(f"\n{'=' * 70}")
    print("COMPLETE")
    print("=" * 70)
    print(f"  Found on Credo:        {stats['found']}")
    print(f"    - Already had URL:   {stats['already_has_url']}")
    print(f"    - URLs updated:      {stats['updated']}")
    print(f"  Not found on Credo:    {stats['not_found']}")
    print(f"  Brand not on Credo:    {stats['brand_not_on_credo']}")
    print(f"  Skipped (gift cards):  {stats['skipped']}")
    print(f"  Total archived:        {stats['archived']}")
    print(f"  Errors:                {stats['errors']}")

    # Save results
    with open("credo_sync_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to credo_sync_results.json")


if __name__ == "__main__":
    main()
