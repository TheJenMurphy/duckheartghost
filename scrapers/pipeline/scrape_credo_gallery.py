#!/usr/bin/env python3
"""
Scrape brand gallery images from Credo Beauty (credobeauty.com).

Uses Playwright (headless browser) to bypass Cloudflare bot protection.
For each brand, fetches products from credobeauty.com/collections/{slug}/products.json
and extracts product hero images for the gallery-2 MultiImage field.

Usage:
    PYTHONUNBUFFERED=1 python3 scrape_credo_gallery.py --dry-run
    PYTHONUNBUFFERED=1 python3 scrape_credo_gallery.py --live
    PYTHONUNBUFFERED=1 python3 scrape_credo_gallery.py --dry-run --only-missing --verbose
    PYTHONUNBUFFERED=1 python3 scrape_credo_gallery.py --live --limit 5 --verbose
"""

import os
import sys
import time
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

import requests

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    sys.exit("ERROR: pip install playwright && python -m playwright install chromium")

WEBFLOW_API_BASE = "https://api.webflow.com/v2"
BRANDS_COLLECTION_ID = "697d981be773ae7dbfc093ed"
CREDO_BASE = "https://credobeauty.com"

MAX_GALLERY_IMAGES = 12


# ---------------------------------------------------------------------------
# Playwright helpers (from scrape_credo_brands.py)
# ---------------------------------------------------------------------------

def safe_goto(page, url, timeout=60000):
    """Navigate to URL with domcontentloaded."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        time.sleep(3)
        return True
    except PlaywrightTimeout:
        print(f"    Timeout loading {url}", flush=True)
        return False
    except Exception as e:
        print(f"    Error loading {url}: {e}", flush=True)
        return False


def normalize_shopify_cdn_url(url: str, width: int = 600) -> str:
    """Normalize Shopify CDN image URL to a consistent size."""
    if 'cdn.shopify.com' not in url:
        return url
    url = re.sub(r'_(\d+x\d*|\d*x\d+|small|medium|large|grande|master|compact|pico|icon)\.', '.', url)
    url = re.sub(r'\.([a-zA-Z]{3,4})(\?|$)', rf'_{width}x.\1\2', url)
    url = re.sub(r'\?v=\d+', '', url)
    return url


# ---------------------------------------------------------------------------
# Credo product scraping via Playwright
# ---------------------------------------------------------------------------

def fetch_credo_products(page, slug: str, verbose: bool = False) -> List[Dict]:
    """Fetch products for a brand from Credo's Shopify JSON API via Playwright."""
    all_products = []
    pg = 1

    while True:
        url = f"{CREDO_BASE}/collections/{slug}/products.json?limit=250&page={pg}"
        if not safe_goto(page, url, timeout=30000):
            break

        try:
            body = page.query_selector("body, pre")
            if not body:
                break
            raw = body.inner_text()
            data = json.loads(raw)
            batch = data.get("products", [])
            all_products.extend(batch)
            if verbose:
                print(f"    [Credo] Page {pg}: {len(batch)} products (total: {len(all_products)})", flush=True)
            if len(batch) < 250:
                break
            pg += 1
            time.sleep(1)
        except (json.JSONDecodeError, Exception) as e:
            if verbose:
                print(f"    [Credo] Page {pg} failed: {e}", flush=True)
            break

    return all_products


def extract_gallery_images(products: List[Dict], verbose: bool = False) -> List[str]:
    """
    Extract hero images from Credo products.
    Picks one product per product_type for variety, then fills remaining slots.
    """
    by_type: Dict[str, List[str]] = {}

    for product in products:
        product_type = (product.get('product_type') or 'unknown').strip().lower()
        images = product.get('images', [])
        if not images:
            continue
        img_url = images[0].get('src', '')
        if not img_url:
            continue
        # Fix protocol-relative URLs
        if img_url.startswith('//'):
            img_url = 'https:' + img_url
        img_url = normalize_shopify_cdn_url(img_url)
        if product_type not in by_type:
            by_type[product_type] = []
        by_type[product_type].append(img_url)

    if verbose:
        print(f"    [Credo] {len(by_type)} product types found", flush=True)

    # Round-robin across product types for variety
    result = []
    seen = set()
    type_lists = list(by_type.values())

    # Pass 1: one from each type
    for imgs in type_lists:
        for img in imgs:
            if img not in seen:
                result.append(img)
                seen.add(img)
                break
        if len(result) >= MAX_GALLERY_IMAGES:
            break

    # Pass 2: fill remaining
    if len(result) < MAX_GALLERY_IMAGES:
        idx = 1
        while len(result) < MAX_GALLERY_IMAGES:
            added = False
            for imgs in type_lists:
                if idx < len(imgs) and imgs[idx] not in seen:
                    result.append(imgs[idx])
                    seen.add(imgs[idx])
                    added = True
                    if len(result) >= MAX_GALLERY_IMAGES:
                        break
            if not added:
                break
            idx += 1

    return result


# ---------------------------------------------------------------------------
# Slug matching: CMS slug -> Credo collection handle
# ---------------------------------------------------------------------------

# Some CMS slugs don't match Credo collection handles. Map known mismatches.
SLUG_OVERRIDES = {
    "tower-28": "tower-28-beauty",
    "ilia": "ilia-beauty",
    "tata-harper": "tata-harper-skincare",
    "pai": "pai-skincare",
    "rms-beauty": "rms-beauty",
}

# Suffixes to try stripping/adding when matching
SLUG_SUFFIXES = ['-beauty', '-skincare', '-skin-care', '-cosmetics', '-makeup', '-hair-care']


def get_credo_slugs(cms_slug: str) -> List[str]:
    """Generate candidate Credo collection slugs from the CMS slug."""
    if cms_slug in SLUG_OVERRIDES:
        return [SLUG_OVERRIDES[cms_slug], cms_slug]

    candidates = [cms_slug]

    # Try stripping common suffixes
    for suffix in SLUG_SUFFIXES:
        if cms_slug.endswith(suffix):
            base = cms_slug[:-len(suffix)]
            candidates.append(base)

    # Try adding common suffixes
    for suffix in SLUG_SUFFIXES[:2]:  # Only try -beauty, -skincare
        candidate = cms_slug + suffix
        if candidate not in candidates:
            candidates.append(candidate)

    return candidates


# ---------------------------------------------------------------------------
# Webflow client
# ---------------------------------------------------------------------------

class WebflowClient:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.site_id = os.environ.get('WEBFLOW_SITE_ID', '')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
        })

    def get_items(self, collection_id: str) -> List[Dict]:
        items = []
        offset = 0
        while True:
            url = f'{WEBFLOW_API_BASE}/collections/{collection_id}/items?limit=100&offset={offset}'
            resp = self.session.get(url)
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get('Retry-After', 60)))
                continue
            if not resp.ok:
                print(f"  Error fetching items: {resp.status_code} {resp.text[:200]}", flush=True)
                break
            data = resp.json()
            batch = data.get('items', [])
            items.extend(batch)
            if len(batch) < 100:
                break
            offset += 100
            time.sleep(0.5)
        return items

    def update_item(self, collection_id: str, item_id: str, field_data: Dict) -> bool:
        url = f'{WEBFLOW_API_BASE}/collections/{collection_id}/items/{item_id}'
        payload = {
            'isArchived': False,
            'isDraft': False,
            'fieldData': field_data,
        }
        resp = self.session.patch(url, json=payload, headers={'Content-Type': 'application/json'})
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get('Retry-After', 60)))
            return self.update_item(collection_id, item_id, field_data)
        if not resp.ok:
            print(f"    Update error {resp.status_code}: {resp.text[:200]}", flush=True)
        return resp.ok

    def publish_items(self, collection_id: str, item_ids: List[str]) -> bool:
        if not self.site_id:
            print("  WEBFLOW_SITE_ID not set, skipping publish", flush=True)
            return False
        for i in range(0, len(item_ids), 100):
            batch = item_ids[i:i + 100]
            url = f'{WEBFLOW_API_BASE}/collections/{collection_id}/items/publish'
            resp = self.session.post(url, json={'itemIds': batch},
                                     headers={'Content-Type': 'application/json'})
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get('Retry-After', 60)))
                resp = self.session.post(url, json={'itemIds': batch},
                                         headers={'Content-Type': 'application/json'})
            if not resp.ok:
                print(f"    Publish error (batch {i // 100 + 1}): {resp.status_code} {resp.text[:200]}", flush=True)
                return False
            print(f"  Published batch {i // 100 + 1} ({len(batch)} items)", flush=True)
            time.sleep(1.0)
        return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape brand gallery images from Credo Beauty")
    parser.add_argument("--dry-run", action="store_true", help="Preview without updating Webflow")
    parser.add_argument("--live", action="store_true", help="Actually update Webflow")
    parser.add_argument("--only-missing", action="store_true", help="Only brands missing gallery images")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of brands")
    parser.add_argument("--verbose", action="store_true", help="Show detailed scraping info")
    args = parser.parse_args()

    if not args.dry_run and not args.live:
        print("Specify --dry-run or --live")
        return

    dry_run = not args.live

    print("=" * 70, flush=True)
    print("CREDO BEAUTY GALLERY SCRAPER", flush=True)
    print("=" * 70, flush=True)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}", flush=True)
    print(f"Source: {CREDO_BASE}", flush=True)
    if args.only_missing:
        print("Filter: only brands missing gallery", flush=True)
    if args.limit:
        print(f"Limit: {args.limit} brands", flush=True)

    # Fetch brands from Webflow
    client = WebflowClient()
    print("\nFetching brands from Webflow...", flush=True)
    brands = client.get_items(BRANDS_COLLECTION_ID)
    print(f"Loaded {len(brands)} brands", flush=True)

    # Filter
    if args.only_missing:
        brands = [b for b in brands if not b.get('fieldData', {}).get('gallery-2')]
        print(f"Brands missing gallery: {len(brands)}", flush=True)

    if args.limit > 0:
        brands = brands[:args.limit]

    print(f"\nProcessing {len(brands)} brands...", flush=True)
    print("=" * 70, flush=True)

    # Launch Playwright
    updated_ids = []
    found_count = 0
    not_on_credo = 0
    no_products = 0
    image_counts = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 720},
        )
        page = context.new_page()

        # Warm up: navigate to Credo homepage first to get cookies/clearance
        print("\nWarming up Playwright (loading Credo homepage)...", flush=True)
        safe_goto(page, CREDO_BASE, timeout=30000)
        time.sleep(2)

        for i, brand in enumerate(brands, 1):
            item_id = brand['id']
            fd = brand.get('fieldData', {})
            name = fd.get('name', 'Unknown')
            slug = fd.get('slug', '')

            has_gallery = bool(fd.get('gallery-2'))
            print(f"\n[{i}/{len(brands)}] {name} (slug: {slug})", flush=True)
            if has_gallery and not args.only_missing:
                existing = fd.get('gallery-2', [])
                print(f"  Already has gallery ({len(existing)} images)", flush=True)

            # Try candidate slugs on Credo
            products = []
            matched_slug = None
            for credo_slug in get_credo_slugs(slug):
                if args.verbose:
                    print(f"  Trying Credo slug: {credo_slug}", flush=True)
                products = fetch_credo_products(page, credo_slug, verbose=args.verbose)
                if products:
                    matched_slug = credo_slug
                    break
                time.sleep(1)

            if not products:
                print(f"  Not found on Credo", flush=True)
                not_on_credo += 1
                continue

            print(f"  Credo collection: {matched_slug} ({len(products)} products)", flush=True)

            # Extract gallery images
            gallery_images = extract_gallery_images(products, verbose=args.verbose)

            if not gallery_images:
                print(f"  No product images found", flush=True)
                no_products += 1
                continue

            print(f"  Gallery: {len(gallery_images)} images", flush=True)
            found_count += 1
            image_counts.append(len(gallery_images))

            if args.verbose:
                for j, url in enumerate(gallery_images):
                    print(f"    [{j+1}] {url[:75]}", flush=True)

            # Build MultiImage array
            gallery_data = [{'url': url} for url in gallery_images]
            field_data = {'gallery-2': gallery_data}

            if not dry_run:
                if client.update_item(BRANDS_COLLECTION_ID, item_id, field_data):
                    print(f"  UPDATED", flush=True)
                    updated_ids.append(item_id)
                else:
                    print(f"  UPDATE FAILED", flush=True)
                time.sleep(0.5)
            else:
                updated_ids.append(item_id)

            time.sleep(2)

        browser.close()

    # Publish
    if not dry_run and updated_ids:
        print(f"\n{'='*70}", flush=True)
        print(f"Publishing {len(updated_ids)} updated brands...", flush=True)
        client.publish_items(BRANDS_COLLECTION_ID, updated_ids)

    # Summary
    print(f"\n{'='*70}", flush=True)
    print("SUMMARY", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"Brands processed:       {len(brands)}", flush=True)
    print(f"Galleries populated:    {found_count}", flush=True)
    print(f"Not on Credo:           {not_on_credo}", flush=True)
    print(f"No product images:      {no_products}", flush=True)
    if image_counts:
        avg = sum(image_counts) / len(image_counts)
        print(f"Avg images per brand:   {avg:.1f}", flush=True)
    print(f"{'Updated' if not dry_run else 'Would update'}: {len(updated_ids)}", flush=True)
    print("\nDone!", flush=True)


if __name__ == "__main__":
    main()
