#!/usr/bin/env python3
"""
Scrape ingredients for makeup products missing ingredient data.

Usage:
    python scrape_missing_makeups_ingredients.py --dry-run --limit 10
    python scrape_missing_makeups_ingredients.py --live
"""

import os
import sys
import time
import re
import json
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse
import functools

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

import requests
print = functools.partial(print, flush=True)

WEBFLOW_API_BASE = "https://api.webflow.com/v2"
MAKEUPS_COLLECTION_ID = "697d3803e654519eef084068"

# Keywords to exclude (non-products)
EXCLUDE_KW = ['brush', 'sponge', 'applicator', 'tool', 'sharpener', 'tweezer', 'curler',
              'set', 'kit', 'duo', 'trio', 'bundle', 'collection', 'essentials', 'routine',
              'crewneck', 'keychain', 'plushie', 'bag', 'pouch', 'case', 'book', 'gift card',
              'sachet', 'capsule', 'supplement', 'vitamin', 'magnesium', 'travel size']


def extract_ingredients_from_html(html: str) -> Optional[str]:
    """Extract ingredients section from HTML using multiple strategies."""
    if not html:
        return None

    # Strategy 1: Look for INCI-style ingredient lists (Water/Aqua followed by scientific names)
    inci_patterns = [
        r'((?:Water|Aqua|Aloe)[A-Za-z0-9,\s\(\)\-\/\.\*\:\'\"]+(?:Fragrance|Parfum|Extract|Oil|Acid|Glycol|Oxide|Alcohol)[A-Za-z0-9,\s\(\)\-\/\.\*]*)',
        r'((?:Aqua|Water)[\/\w\s,\(\)\-\.\*]{100,2000})',
    ]

    for pattern in inci_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            # Clean up the match
            clean = re.sub(r'\\u[0-9a-fA-F]{4}', '', m)
            clean = re.sub(r'<[^>]+>', ' ', clean)
            clean = re.sub(r'&[a-z]+;', ' ', clean)
            clean = re.sub(r'\s+', ' ', clean).strip()

            # Remove trailing non-ingredient text
            cutoffs = ['how to', 'directions', 'apply', 'use:', 'benefits', 'warning',
                      'caution', 'storage', 'made in', 'certified', '*organic', '**']
            for cutoff in cutoffs:
                idx = clean.lower().find(cutoff)
                if idx > 50:
                    clean = clean[:idx].strip()

            clean = clean.rstrip('., ;:*')

            # Validate - should have commas and look like ingredients
            if ',' in clean and len(clean) > 50 and len(clean) < 3000:
                # Check it has ingredient-like words
                if re.search(r'(glycerin|extract|oil|acid|water|aqua)', clean, re.I):
                    return clean

    # Strategy 2: Find "ingredients" section and extract
    html_lower = html.lower()

    for keyword in ['full ingredients', 'ingredients:', 'ingredients list', 'inci:']:
        pos = html_lower.find(keyword)
        if pos != -1:
            after_ing = html[pos:pos + 3000]

            # Remove HTML
            clean = re.sub(r'<script[^>]*>.*?</script>', '', after_ing, flags=re.DOTALL | re.I)
            clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.I)
            clean = re.sub(r'<[^>]+>', ' ', clean)
            clean = re.sub(r'&[a-z]+;', ' ', clean)
            clean = re.sub(r'\\u[0-9a-fA-F]{4}', '', clean)
            clean = re.sub(r'\s+', ' ', clean).strip()

            # Skip past label
            match = re.match(r'^(?:full\s+)?ingredients?\s*(?:list)?\s*:?\s*', clean, re.I)
            if match:
                clean = clean[match.end():]

            # Find cutoff
            cutoffs = ['how to use', 'directions', 'benefits', 'warning', 'caution',
                      'shipping', 'returns', 'reviews', 'add to cart', 'share']
            for cutoff in cutoffs:
                idx = clean.lower().find(cutoff)
                if idx > 30:
                    clean = clean[:idx].strip()
                    break

            clean = clean[:2000].rstrip('., ;:')

            if ',' in clean and len(clean) > 50:
                if re.search(r'(glycerin|extract|oil|acid|water|aqua)', clean, re.I):
                    return clean

    return None


def fetch_product_data(url: str) -> Optional[Dict]:
    """Fetch product data from URL - prefers full HTML for better ingredient extraction."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    # Try full HTML page first (more likely to have ingredients)
    try:
        resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 5000:
            return {'body_html': resp.text, 'source': 'html'}
    except Exception as e:
        pass

    # Fall back to Shopify JSON
    try:
        json_url = url.rstrip('/') + '.json'
        resp = requests.get(json_url, headers={**headers, 'Accept': 'application/json'},
                          timeout=15, allow_redirects=True)
        if resp.status_code == 200:
            try:
                data = resp.json()
                product = data.get('product', data)
                if product.get('body_html'):
                    product['source'] = 'json'
                    return product
            except:
                pass
    except:
        pass

    return None


def extract_ingredients(product_data: Dict) -> Optional[str]:
    """Extract ingredients from product data."""
    if not product_data:
        return None

    body_html = product_data.get('body_html', '') or ''
    ingredients = extract_ingredients_from_html(body_html)
    if ingredients:
        return ingredients

    # Check metafields
    metafields = product_data.get('metafields', []) or []
    for mf in metafields:
        if isinstance(mf, dict):
            key = (mf.get('key', '') or '').lower()
            if 'ingredient' in key:
                val = mf.get('value', '')
                if val and len(val) > 20:
                    return val

    return None


class WebflowClient:
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
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
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

    def get_all_items(self) -> List[Dict]:
        items = []
        offset = 0
        while True:
            result = self._request('GET', f'/collections/{MAKEUPS_COLLECTION_ID}/items?limit=100&offset={offset}')
            if not result or not result.get('items'):
                break
            items.extend(result['items'])
            if len(result['items']) < 100:
                break
            offset += 100
        return items

    def update_item(self, item_id: str, field_data: Dict) -> bool:
        data = {
            'isArchived': False,
            'isDraft': False,
            'fieldData': field_data
        }
        result = self._request('PATCH', f'/collections/{MAKEUPS_COLLECTION_ID}/items/{item_id}', json_data=data)
        return result is not None


def main():
    print("=" * 70)
    print("SCRAPE MISSING MAKEUP INGREDIENTS")
    print("=" * 70)

    args = sys.argv[1:]
    dry_run = '--live' not in args

    limit = None
    offset = 0
    for i, arg in enumerate(args):
        if arg == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1])
        if arg == '--offset' and i + 1 < len(args):
            offset = int(args[i + 1])

    if dry_run:
        print("Mode: DRY RUN")
    else:
        print("Mode: LIVE")

    client = WebflowClient()

    print("\nLoading makeups collection...")
    items = client.get_all_items()
    print(f"  Found {len(items)} products")

    # Find products missing ingredients
    missing = []
    for item in items:
        fd = item.get('fieldData', {})
        name = fd.get('name', '')
        text = fd.get('ingredients-2', '') or ''
        url = fd.get('external-link', '') or ''

        # Skip if has ingredients
        if text.strip() and len(text.strip()) > 10:
            continue

        # Skip non-products
        name_lower = name.lower()
        if any(kw in name_lower for kw in EXCLUDE_KW):
            continue

        # Skip if no URL
        if not url:
            continue

        missing.append({
            'id': item['id'],
            'name': name,
            'url': url
        })

    print(f"  Products to scrape: {len(missing)}")

    if offset:
        missing = missing[offset:]
        print(f"  Starting from offset: {offset}")

    if limit:
        missing = missing[:limit]
        print(f"  Limited to: {limit}")

    # Scrape each product
    success = 0
    failed = 0
    no_ingredients = 0

    for i, product in enumerate(missing):
        print(f"\n[{i+1}/{len(missing)}] {product['name'][:50]}")
        print(f"  URL: {product['url'][:60]}...")

        # Fetch product data
        data = fetch_product_data(product['url'])
        if not data:
            print("  ✗ Failed to fetch")
            failed += 1
            continue

        # Extract ingredients
        ingredients = extract_ingredients(data)
        if not ingredients:
            print("  ✗ No ingredients found")
            no_ingredients += 1
            continue

        print(f"  ✓ Found {len(ingredients)} chars: {ingredients[:60]}...")

        # Update Webflow
        if not dry_run:
            if client.update_item(product['id'], {'ingredients-2': ingredients}):
                print("  ✓ Updated in Webflow")
                success += 1
            else:
                print("  ✗ Failed to update")
                failed += 1
        else:
            success += 1

        # Small delay between requests
        time.sleep(0.3)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Scraped: {len(missing)}")
    print(f"  Success: {success}")
    print(f"  No ingredients found: {no_ingredients}")
    print(f"  Failed: {failed}")

    if dry_run:
        print("\n[DRY RUN] No changes made. Run with --live to apply.")


if __name__ == '__main__':
    main()
