#!/usr/bin/env python3
"""
Scrape source attributes (ownership info) from brand websites.

Looks for woman-owned, BIPOC-owned, family-owned, etc. on brand About pages.

Usage:
    python scrape_source_attributes.py --dry-run
    python scrape_source_attributes.py --live
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
BRANDS_COLLECTION_ID = "67d1b1e4b94243aa9c881b7a"

# Brand website base URLs
BRAND_WEBSITES = {
    "Tower 28 Beauty": "https://www.tower28beauty.com",
    "Kosas": "https://kosas.com",
    "Ilia Beauty": "https://iliabeauty.com",
    "RMS Beauty": "https://www.rmsbeauty.com",
    "Westman Atelier": "https://www.westman-atelier.com",
    "Tata Harper Skincare": "https://www.tataharperskincare.com",
    "Indie Lee": "https://www.indielee.com",
    "True Botanicals": "https://truebotanicals.com",
    "Osea": "https://www.oseamalibu.com",
    "OSEA": "https://www.oseamalibu.com",
    "Marie Veronique": "https://www.marieveronique.com",
    "Ursa Major": "https://www.ursamajorvt.com",
    "lys BEAUTY": "https://www.lysbeauty.com",
    "LYS Beauty": "https://www.lysbeauty.com",
    "Jillian Dempsey": "https://www.jilliandempsey.com",
    "Necessaire": "https://www.necessaire.com",
    "Gen See": "https://gensee.co",
    "Mob Beauty": "https://mobbeauty.com",
    "MOB Beauty": "https://mobbeauty.com",
    "Grown Alchemist": "https://www.grownalchemist.com",
    "Soshe Beauty": "https://www.soshebeauty.com",
    "Finding Ferdinand": "https://www.findingferdinand.com",
    "Exa": "https://www.exabeauty.com",
}

# Patterns to detect ownership
SOURCE_PATTERNS = {
    'woman-owned': [
        r'woman[\s-]?owned',
        r'women[\s-]?owned',
        r'female[\s-]?founded',
        r'woman[\s-]?founded',
        r'founded by (?:a )?wom[ae]n',
        r'female entrepreneur',
    ],
    'bipoc-owned': [
        r'(?:bipoc|black|african[\s-]?american|latina?o?|asian|indigenous)[\s-]?owned',
        r'(?:bipoc|black|african[\s-]?american|latina?o?|asian|indigenous)[\s-]?founded',
        r'founded by (?:a )?(?:black|african[\s-]?american|latina?o?|asian|indigenous)',
        r'minority[\s-]?owned',
    ],
    'family-owned': [
        r'family[\s-]?owned',
        r'family[\s-]?run',
        r'family business',
        r'family[\s-]?operated',
    ],
    'indie-brand': [
        r'indie(?:pendent)? brand',
        r'independent(?:ly owned)?',
        r'small batch',
        r'artisan',
    ],
    'celebrity-founded': [
        r'celebrity[\s-]?founded',
        r'founded by [\w\s]+ (?:actress|actor|singer|model|influencer)',
    ],
}


def fetch_about_page(base_url: str) -> Optional[str]:
    """Fetch brand's about page content."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    # Try common about page URLs
    about_paths = ['/pages/about', '/pages/about-us', '/about', '/about-us', '/pages/our-story', '/our-story']

    for path in about_paths:
        try:
            url = base_url.rstrip('/') + path
            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            if resp.status_code == 200 and len(resp.text) > 5000:
                return resp.text
        except:
            pass

    # Also try homepage
    try:
        resp = requests.get(base_url, headers=headers, timeout=15, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except:
        pass

    return None


def detect_source_attributes(html: str) -> Set[str]:
    """Detect source attributes from page content."""
    if not html:
        return set()

    # Clean HTML - remove scripts/styles
    clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.I)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.I)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).lower()

    found = set()

    for attr, patterns in SOURCE_PATTERNS.items():
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
        self._brand_cache = {}

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

    def load_brands(self):
        print("Loading brands...")
        offset = 0
        while True:
            result = self._request('GET', f'/collections/{BRANDS_COLLECTION_ID}/items?limit=100&offset={offset}')
            if not result or not result.get('items'):
                break
            for item in result['items']:
                fd = item.get('fieldData', {})
                self._brand_cache[item.get('id')] = fd.get('name', '')
            if len(result['items']) < 100:
                break
            offset += 100
        print(f"  Loaded {len(self._brand_cache)} brands")

    def get_brand_name(self, brand_ref):
        if isinstance(brand_ref, list) and brand_ref:
            return self._brand_cache.get(brand_ref[0], '')
        elif isinstance(brand_ref, str):
            return self._brand_cache.get(brand_ref, '')
        return ''

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
    print("SCRAPE SOURCE ATTRIBUTES FROM BRAND WEBSITES")
    print("=" * 70)
    print()

    args = sys.argv[1:]
    dry_run = '--live' not in args

    if '--dry-run' not in args and '--live' not in args:
        print(__doc__)
        return

    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print()

    updater = WebflowUpdater()
    updater.load_brands()
    products = updater.get_all_products()
    print()

    # First, scrape brand about pages
    print("Scraping brand about pages...")
    brand_sources = {}
    for brand_name, base_url in BRAND_WEBSITES.items():
        print(f"  {brand_name}...", end=' ')
        html = fetch_about_page(base_url)
        if html:
            sources = detect_source_attributes(html)
            if sources:
                brand_sources[brand_name] = sources
                print(f"found: {', '.join(sources)}")
            else:
                print("no ownership info found")
        else:
            print("failed to fetch")
        time.sleep(0.5)

    print()
    print(f"Brands with source attributes: {len(brand_sources)}")
    print()

    if not brand_sources:
        print("No source attributes found!")
        return

    # Find products missing source-attributes that belong to brands with known sources
    to_update = []
    for item in products:
        fd = item.get('fieldData', {})
        source_attrs = (fd.get('source-attributes', '') or '').strip()

        # Skip if already has source attributes
        if source_attrs:
            continue

        brand_ref = fd.get('brand', [])
        brand_name = updater.get_brand_name(brand_ref)

        if brand_name in brand_sources:
            to_update.append((item, brand_sources[brand_name]))

    print(f"Products to update with source attributes: {len(to_update)}")
    print()

    if not to_update:
        print("No products to update!")
        return

    updated = 0
    for i, (item, sources) in enumerate(to_update, 1):
        item_id = item['id']
        fd = item.get('fieldData', {})
        name = fd.get('name', 'Unknown')

        source_str = ', '.join(sorted(sources))

        if i <= 20 or i % 100 == 0:
            print(f"[{i}/{len(to_update)}] {name[:40]}")
            print(f"  source-attributes: {source_str}")

        if not dry_run:
            if updater.update_product(item_id, {'source-attributes': source_str}):
                updated += 1
        else:
            updated += 1

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Products processed: {len(to_update)}")
    print(f"{'Would update' if dry_run else 'Updated'}: {updated}")

    if dry_run:
        print()
        print("[DRY RUN] No changes made. Run with --live to apply.")


if __name__ == '__main__':
    main()
