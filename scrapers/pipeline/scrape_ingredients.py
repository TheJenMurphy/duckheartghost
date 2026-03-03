#!/usr/bin/env python3
"""
Scrape ingredients from brand product pages.

Uses the product-url field to fetch product data from Shopify .json endpoints
and extracts ingredient lists.

Usage:
    python scrape_ingredients.py --dry-run --limit 10
    python scrape_ingredients.py --live --all
"""

import os
import sys
import time
import re
import json
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

import requests
import functools
print = functools.partial(print, flush=True)

WEBFLOW_API_BASE = "https://api.webflow.com/v2"
PRODUCTS_COLLECTION_ID = "67b260cb70f3225a0a29e7e2"


def extract_ingredients_from_html(html: str) -> Optional[str]:
    """Extract ingredients section from HTML."""
    if not html:
        return None

    html_lower = html.lower()

    # Find "ingredients" keyword position - try multiple variations
    ing_pos = -1
    for keyword in ['full ingredient', 'ingredients:', 'ingredients<', 'ingredients\n', 'ingredients ']:
        pos = html_lower.find(keyword)
        if pos != -1 and (ing_pos == -1 or pos < ing_pos):
            ing_pos = pos

    if ing_pos == -1:
        # Try just "ingredients" as last resort
        ing_pos = html_lower.find('ingredients')

    if ing_pos == -1:
        return None

    # Get text after "ingredients" - take more context
    after_ing = html[ing_pos:ing_pos + 3000]

    # Remove script/style tags first
    after_ing = re.sub(r'<script[^>]*>.*?</script>', '', after_ing, flags=re.DOTALL | re.I)
    after_ing = re.sub(r'<style[^>]*>.*?</style>', '', after_ing, flags=re.DOTALL | re.I)

    # Remove HTML tags and clean up
    clean = re.sub(r'<[^>]+>', ' ', after_ing)
    clean = re.sub(r'&[a-z]+;', ' ', clean)  # HTML entities
    clean = re.sub(r'\s+', ' ', clean).strip()

    # Skip past "ingredients:" label
    match = re.match(r'^(?:full\s+)?ingredients?\s*:?\s*', clean, re.I)
    if match:
        clean = clean[match.end():]

    # Take first 2000 chars as potential ingredients
    clean = clean[:2000]

    # Validate it looks like an ingredient list
    if len(clean) < 20:
        return None

    # Find a good cutoff point - often ends before these phrases
    cutoffs = [
        'how to use', 'how to apply', 'directions', 'usage', 'application',
        'benefits', 'about this', 'what it does', 'why we love', 'details',
        'shipping', 'returns', 'reviews', 'you may also', 'customers also',
        'add to cart', 'add to bag', 'share this', 'pin it'
    ]
    for cutoff in cutoffs:
        idx = clean.lower().find(cutoff)
        if idx > 30:
            clean = clean[:idx].strip()
            break

    # Clean up trailing punctuation
    clean = clean.rstrip('., ;:')

    # Validate - should have commas (ingredient lists are comma-separated)
    if ',' in clean and len(clean) > 30:
        return clean

    return None


def fetch_shopify_product(url: str) -> Optional[Dict]:
    """Fetch product data from Shopify JSON endpoint or HTML page."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    # Try JSON endpoint first
    try:
        json_url = url.rstrip('/') + '.json'
        resp = requests.get(json_url, headers={**headers, 'Accept': 'application/json'}, timeout=15, allow_redirects=True)

        if resp.status_code == 200:
            try:
                data = resp.json()
                product = data.get('product', data)
                if product.get('body_html'):
                    return product
            except:
                pass
    except:
        pass

    # Fall back to HTML page
    try:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        # Accept any response with substantial content
        if len(resp.text) > 10000:
            return {'body_html': resp.text}
    except:
        pass

    return None


def extract_ingredients(product_data: Dict) -> Optional[str]:
    """Extract ingredients from Shopify product data."""
    if not product_data:
        return None

    # Check body_html first
    body_html = product_data.get('body_html', '') or ''
    ingredients = extract_ingredients_from_html(body_html)
    if ingredients:
        return ingredients

    # Check metafields if available
    metafields = product_data.get('metafields', []) or []
    for mf in metafields:
        if isinstance(mf, dict):
            key = (mf.get('key', '') or '').lower()
            if 'ingredient' in key:
                val = mf.get('value', '')
                if val and len(val) > 20:
                    return val

    # Check tags for ingredient info
    tags = product_data.get('tags', '') or ''
    if isinstance(tags, list):
        tags = ', '.join(tags)

    return None


class WebflowUpdater:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
        })
        self._last_request = 0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_request = time.time()

    def _request(self, method: str, endpoint: str, json_data=None):
        self._rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'

        headers = dict(self.session.headers)
        if json_data:
            headers['Content-Type'] = 'application/json'
            resp = self.session.request(method, url, json=json_data, headers=headers)
        else:
            resp = self.session.request(method, url, headers=headers)

        if resp.status_code == 429:
            wait = int(resp.headers.get('Retry-After', 60))
            print(f'Rate limited. Waiting {wait}s...')
            time.sleep(wait)
            return self._request(method, endpoint, json_data)

        if not resp.ok:
            return None

        return resp.json() if resp.text else {}

    def get_all_products(self) -> List[Dict]:
        print("Loading products...")
        items = []
        offset = 0
        while True:
            result = self._request('GET', f'/collections/{PRODUCTS_COLLECTION_ID}/items?limit=100&offset={offset}')
            if not result or not result.get('items'):
                break
            items.extend(result['items'])
            print(f"  Loaded {len(items)}...", end='\r')
            if len(result['items']) < 100:
                break
            offset += 100
        print(f"  Loaded {len(items)} products total")
        return items

    def update_product(self, item_id: str, field_data: Dict) -> bool:
        data = {
            'isArchived': False,
            'isDraft': False,
            'fieldData': field_data
        }
        result = self._request('PATCH', f'/collections/{PRODUCTS_COLLECTION_ID}/items/{item_id}', json_data=data)
        return result is not None


def main():
    print("=" * 70)
    print("SCRAPE INGREDIENTS FROM BRAND WEBSITES")
    print("=" * 70)
    print()

    args = sys.argv[1:]
    dry_run = '--live' not in args

    if '--dry-run' not in args and '--live' not in args:
        print(__doc__)
        return

    limit = None
    for i, arg in enumerate(args):
        if arg == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1])
        elif arg == '--all':
            limit = None

    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    if limit:
        print(f"Limit: {limit}")
    print()

    updater = WebflowUpdater()
    products = updater.get_all_products()
    print()

    # Find products missing ingredients but having product-url
    to_process = []
    for item in products:
        fd = item.get('fieldData', {})
        ingredients = (fd.get('ingredients-2', '') or '').strip()
        product_url = (fd.get('product-url', '') or '').strip()

        if not ingredients and product_url:
            to_process.append(item)

    print(f"Products missing ingredients (with URL): {len(to_process)}")

    if limit:
        to_process = to_process[:limit]
        print(f"Processing: {len(to_process)}")
    print()

    if not to_process:
        print("All products have ingredients!")
        return

    updated = 0
    skipped = 0
    errors = 0

    for i, item in enumerate(to_process, 1):
        item_id = item['id']
        fd = item.get('fieldData', {})
        name = fd.get('name', 'Unknown')
        product_url = fd.get('product-url', '')

        if i <= 20 or i % 50 == 0:
            print(f"[{i}/{len(to_process)}] {name[:45]}")

        # Fetch product data from brand website
        product_data = fetch_shopify_product(product_url)

        if not product_data:
            if i <= 20:
                print(f"  (no data)")
            errors += 1
            time.sleep(0.5)
            continue

        # Extract ingredients
        ingredients = extract_ingredients(product_data)

        if not ingredients:
            if i <= 20:
                print(f"  (no ingredients found)")
            skipped += 1
            time.sleep(0.3)
            continue

        # Truncate if too long
        if len(ingredients) > 2000:
            ingredients = ingredients[:2000].rsplit(',', 1)[0]

        if i <= 20 or i % 50 == 0:
            preview = ingredients[:60].replace('\n', ' ')
            print(f"  Found: {preview}...")

        if not dry_run:
            if updater.update_product(item_id, {'ingredients-2': ingredients}):
                updated += 1
            else:
                errors += 1
        else:
            updated += 1

        time.sleep(0.3)

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Products processed: {len(to_process)}")
    print(f"{'Would update' if dry_run else 'Updated'}: {updated}")
    print(f"No ingredients found: {skipped}")
    print(f"Errors: {errors}")

    if dry_run:
        print()
        print("[DRY RUN] No changes made. Run with --live to apply.")


if __name__ == '__main__':
    main()
