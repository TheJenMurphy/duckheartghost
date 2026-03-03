#!/usr/bin/env python3
"""
Scrape stars attributes (bestseller, award-winning, etc.) from brand product pages.

Usage:
    python scrape_stars_attributes.py --dry-run --limit 10
    python scrape_stars_attributes.py --live --all
"""

import os
import sys
import time
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

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

# Patterns to detect stars attributes
STARS_PATTERNS = {
    'best-seller': [
        r'best\s*sell(?:er|ing)',
        r'#\s*1\s+sell(?:er|ing)',
        r'top\s+sell(?:er|ing)',
        r'fan\s+favou?rite',
        r'customer\s+favou?rite',
        r'most\s+loved',
        r'most\s+popular',
    ],
    'award-winning': [
        r'award[\s-]*winn(?:er|ing)',
        r'allure\s+(?:best\s+of\s+)?beauty',
        r'beauty\s+award',
        r'editor[\'\u2019]?s?\s+(?:choice|pick)',
        r'won\s+(?:the\s+)?(?:\d+\s+)?award',
        r'prize[\s-]*winn(?:er|ing)',
    ],
    'trending': [
        r'trend(?:ing)?(?:\s+now)?',
        r'viral',
        r'tiktok\s+famous',
        r'social\s+media\s+sensation',
        r'going\s+viral',
    ],
    'top-rated': [
        r'top[\s-]*rated',
        r'highly[\s-]*rated',
        r'5[\s-]*star',
        r'five[\s-]*star',
        r'★{4,5}',
        r'4\.[5-9]\s*(?:out\s+of\s+5|stars?|\/5)',
    ],
    'clinically-proven': [
        r'clinic(?:al)?ly[\s-]*(?:proven|tested|shown)',
        r'dermatologist[\s-]*tested',
        r'scientifically[\s-]*proven',
        r'lab[\s-]*tested',
    ],
    'expert-recommended': [
        r'expert[\s-]*recommend',
        r'dermatologist[\s-]*recommend',
        r'doctor[\s-]*recommend',
        r'professional[\s-]*recommend',
        r'make[\s-]*up\s+artist[\s-]*(?:approved|recommend|pick)',
    ],
}


def fetch_product_page(url: str) -> Optional[str]:
    """Fetch product page HTML."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        if len(resp.text) > 5000:
            return resp.text
    except:
        pass

    return None


def detect_stars_attributes(html: str) -> Set[str]:
    """Detect stars attributes from page content."""
    if not html:
        return set()

    # Clean HTML - remove scripts/styles
    clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.I)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.I)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = re.sub(r'&[a-z]+;', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).lower()

    found = set()

    for attr, patterns in STARS_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, clean, re.I):
                found.add(attr)
                break

    return found


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
    print("SCRAPE STARS ATTRIBUTES FROM BRAND WEBSITES")
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

    # Find products missing stars-attributes but having product-url
    to_process = []
    for item in products:
        fd = item.get('fieldData', {})
        stars = (fd.get('stars-attributes-2', '') or '').strip()
        product_url = (fd.get('product-url', '') or '').strip()

        if not stars and product_url:
            to_process.append(item)

    print(f"Products missing stars-attributes (with URL): {len(to_process)}")

    if limit:
        to_process = to_process[:limit]
        print(f"Processing: {len(to_process)}")
    print()

    if not to_process:
        print("All products have stars-attributes!")
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

        # Fetch product page
        html = fetch_product_page(product_url)

        if not html:
            if i <= 20:
                print(f"  (fetch failed)")
            errors += 1
            time.sleep(0.3)
            continue

        # Detect stars attributes
        stars = detect_stars_attributes(html)

        if not stars:
            if i <= 20:
                print(f"  (no stars found)")
            skipped += 1
            time.sleep(0.2)
            continue

        stars_str = ', '.join(sorted(stars))

        if i <= 20 or i % 50 == 0:
            print(f"  Found: {stars_str}")

        if not dry_run:
            if updater.update_product(item_id, {'stars-attributes-2': stars_str}):
                updated += 1
            else:
                errors += 1
        else:
            updated += 1

        time.sleep(0.2)

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Products processed: {len(to_process)}")
    print(f"{'Would update' if dry_run else 'Updated'}: {updated}")
    print(f"No stars found: {skipped}")
    print(f"Errors: {errors}")

    if dry_run:
        print()
        print("[DRY RUN] No changes made. Run with --live to apply.")


if __name__ == '__main__':
    main()
