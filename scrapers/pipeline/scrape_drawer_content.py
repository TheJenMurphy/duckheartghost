#!/usr/bin/env python3
"""
Scrape drawer content (what it is, who it's for, how to use it) from brand websites.

Usage:
    python scrape_drawer_content.py --limit 50
    python scrape_drawer_content.py --brand "Tata Harper Skincare"
    python scrape_drawer_content.py --all
"""

import os
import re
import time
import json
import requests
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# APIs
WEBFLOW_API_BASE = "https://api.webflow.com/v2"
PRODUCTS_COLLECTION_ID = "67b260cb70f3225a0a29e7e2"
BRANDS_COLLECTION_ID = "67d1b1e4b94243aa9c881b7a"

# Brand website mappings
BRAND_DOMAINS = {
    "Tower 28 Beauty": "tower28beauty.com",
    "Kosas": "kosas.com",
    "Ilia Beauty": "iliabeauty.com",
    "RMS Beauty": "rmsbeauty.com",
    "Westman Atelier": "westman-atelier.com",
    "Tata Harper Skincare": "tataharperskincare.com",
    "Indie Lee": "indielee.com",
    "True Botanicals": "truebotanicals.com",
    "Osea": "oseamalibu.com",
    "Marie Veronique": "marieveronique.com",
    "Ursa Major": "ursamajorvt.com",
    "lys BEAUTY": "lysbeauty.com",
    "Jillian Dempsey": "jilliandempsey.com",
    "Necessaire": "necessaire.com",
    "Gen See": "gensee.co",
    "Mob Beauty": "mobbeauty.com",
    "Grown Alchemist": "grownalchemist.com",
    "Soshe Beauty": "soshebeauty.com",
    "Finding Ferdinand": "findingferdinand.com",
    "Exa": "exabeauty.com",
}

# Accessory keywords - skip these
ACCESSORIES = [
    'brush', 'sponge', 'bag', 'pouch', 'keychain', 'mirror', 'case', 'holder',
    'tool', 'applicator', 'gift card', 'trucker', 'hat', 'cap', 'tote',
    'sock', 'headband', 'scrunchie', 'towel', 'cloth', 'zine', 'print',
    'sharpener', 'test -', 'parent item', 'charm', 'stone', 'bandana',
    'wristlet', 'gift wrap', 'tissue paper', 'card insert', 'pr box',
]


class DrawerContentScraper:
    """Scrape drawer content from brand websites."""

    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.webflow = requests.Session()
        self.webflow.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        })

        self.http = requests.Session()
        self.http.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })

        self._last_webflow = 0
        self._last_http = 0
        self._brand_cache = {}
        self._load_brands()

    def _load_brands(self):
        print("Loading brands...")
        offset = 0
        while True:
            self._rate_limit('webflow')
            resp = self.webflow.get(f'{WEBFLOW_API_BASE}/collections/{BRANDS_COLLECTION_ID}/items?limit=100&offset={offset}')
            if not resp.ok:
                break
            data = resp.json()
            items = data.get('items', [])
            if not items:
                break
            for item in items:
                fd = item.get('fieldData', {})
                self._brand_cache[item.get('id')] = fd.get('name', '')
            offset += 100
            if len(items) < 100:
                break
        print(f"  Loaded {len(self._brand_cache)} brands")

    def _rate_limit(self, kind):
        if kind == 'webflow':
            elapsed = time.time() - self._last_webflow
            if elapsed < 0.5:
                time.sleep(0.5 - elapsed)
            self._last_webflow = time.time()
        else:
            elapsed = time.time() - self._last_http
            if elapsed < 3.0:  # Be nice to brand sites
                time.sleep(3.0 - elapsed)
            self._last_http = time.time()

    def is_accessory(self, name):
        name_lower = name.lower()
        return any(kw in name_lower for kw in ACCESSORIES)

    def get_brand_name(self, brand_ref):
        if isinstance(brand_ref, list) and brand_ref:
            return self._brand_cache.get(brand_ref[0], '')
        elif isinstance(brand_ref, str):
            return self._brand_cache.get(brand_ref, '')
        return ''

    def make_slug(self, name):
        """Convert product name to URL slug."""
        slug = name.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')

    def extract_drawer_content(self, html, brand_name):
        """Extract drawer content from HTML."""
        if not html:
            return {}

        content = {}

        # Try to extract from JSON data first (most reliable)
        json_patterns = [
            r'"description"\s*:\s*"([^"]{20,})"',
            r'"body_html"\s*:\s*"([^"]{50,})"',
        ]

        for pattern in json_patterns:
            match = re.search(pattern, html, re.I)
            if match:
                desc = match.group(1)
                desc = desc.replace('\\u003c', '<').replace('\\u003e', '>')
                desc = desc.replace('\\n', '\n').replace('\\/', '/')
                desc = re.sub(r'\\u[0-9a-fA-F]{4}', '', desc)

                # Clean HTML tags for plain text
                plain = re.sub(r'<[^>]+>', ' ', desc)
                plain = re.sub(r'\s+', ' ', plain).strip()

                if len(plain) > 30:
                    content['description'] = plain[:500]
                break

        # Look for specific sections in HTML
        section_patterns = {
            'what_it_is': [
                r'(?:what\s*it\s*is|description|about)[:\s]*</?\w+[^>]*>\s*([^<]{30,500})',
                r'<p[^>]*class="[^"]*description[^"]*"[^>]*>([^<]{30,500})</p>',
            ],
            'who_its_for': [
                r'(?:who\s*it\'?s?\s*for|ideal\s*for|great\s*for|best\s*for)[:\s]*</?\w+[^>]*>\s*([^<]{20,300})',
                r'(?:skin\s*type|suitable\s*for)[:\s]*</?\w+[^>]*>\s*([^<]{20,200})',
            ],
            'how_to_use': [
                r'(?:how\s*to\s*use|directions|usage|application)[:\s]*</?\w+[^>]*>\s*([^<]{30,500})',
                r'<p[^>]*class="[^"]*directions[^"]*"[^>]*>([^<]{30,500})</p>',
            ],
            'key_ingredients': [
                r'(?:key\s*ingredients?|what\'?s?\s*in\s*it|hero\s*ingredients?)[:\s]*</?\w+[^>]*>\s*([^<]{30,400})',
            ],
        }

        for field, patterns in section_patterns.items():
            if field not in content:
                for pattern in patterns:
                    match = re.search(pattern, html, re.I | re.DOTALL)
                    if match:
                        text = match.group(1)
                        text = re.sub(r'<[^>]+>', ' ', text)
                        text = re.sub(r'&\w+;', ' ', text)
                        text = re.sub(r'\s+', ' ', text).strip()
                        if len(text) > 20:
                            content[field] = text[:500]
                            break

        return content

    def scrape_product(self, product_name, product_slug, brand_name):
        """Scrape drawer content for a product."""
        domain = BRAND_DOMAINS.get(brand_name)
        if not domain:
            return {}

        # Build possible URLs
        name_slug = self.make_slug(product_name)

        # Clean the webflow slug
        clean_slug = product_slug
        brand_slug = self.make_slug(brand_name)
        if clean_slug.startswith(brand_slug + '-'):
            clean_slug = clean_slug[len(brand_slug)+1:]
        clean_slug = re.sub(r'-[a-f0-9]{5,6}$', '', clean_slug)

        slugs = list(dict.fromkeys([clean_slug, name_slug, product_slug]))

        for slug in slugs[:2]:  # Try first 2 slugs only
            for prefix in ['www.', '']:
                url = f'https://{prefix}{domain}/products/{slug}'
                try:
                    self._rate_limit('http')
                    resp = self.http.get(url, timeout=15, allow_redirects=True)
                    if resp.ok and '404' not in resp.text[:1000].lower() and 'not found' not in resp.text[:1000].lower():
                        content = self.extract_drawer_content(resp.text, brand_name)
                        if content:
                            return content
                except Exception as e:
                    continue

        return {}

    def get_products_missing_drawer(self, limit=None, brand_filter=None):
        """Get products missing drawer content."""
        products = []
        offset = 0

        while True:
            self._rate_limit('webflow')
            resp = self.webflow.get(f'{WEBFLOW_API_BASE}/collections/{PRODUCTS_COLLECTION_ID}/items?limit=100&offset={offset}')
            if not resp.ok:
                break
            data = resp.json()
            items = data.get('items', [])
            if not items:
                break

            for item in items:
                fd = item.get('fieldData', {})
                name = fd.get('name', '')
                brand_name = self.get_brand_name(fd.get('brand', []))

                # Apply brand filter if specified
                if brand_filter and brand_name != brand_filter:
                    continue

                # Skip accessories
                if self.is_accessory(name):
                    continue

                # Check if missing drawer content
                what_it_is = fd.get('what-it-is-2', '') or ''
                if what_it_is.strip() and len(what_it_is.strip()) > 10:
                    continue

                # Skip if no brand domain
                if brand_name not in BRAND_DOMAINS:
                    continue

                products.append(item)

            offset += 100
            if len(items) < 100:
                break
            if limit and len(products) >= limit:
                break

        return products[:limit] if limit else products

    def update_product(self, item_id, content):
        """Update product with drawer content."""
        update_data = {'fieldData': {}}

        if content.get('description'):
            update_data['fieldData']['what-it-is-2'] = f"<p>{content['description']}</p>"
        if content.get('what_it_is'):
            update_data['fieldData']['what-it-is-2'] = f"<p>{content['what_it_is']}</p>"
        if content.get('who_its_for'):
            update_data['fieldData']['who-it-s-for-5'] = f"<p>{content['who_its_for']}</p>"
        if content.get('how_to_use'):
            update_data['fieldData']['how-to-use-it-7'] = f"<p>{content['how_to_use']}</p>"
        if content.get('key_ingredients'):
            update_data['fieldData']['what-s-in-it'] = f"<p>{content['key_ingredients']}</p>"

        if not update_data['fieldData']:
            return False

        self._rate_limit('webflow')
        resp = self.webflow.patch(
            f'{WEBFLOW_API_BASE}/collections/{PRODUCTS_COLLECTION_ID}/items/{item_id}',
            json=update_data
        )
        return resp.ok

    def run(self, limit=None, brand_filter=None):
        print(f"\nFetching products missing drawer content...")
        if brand_filter:
            print(f"  Filtering by brand: {brand_filter}")

        products = self.get_products_missing_drawer(limit, brand_filter)
        print(f"Found {len(products)} products to process\n")

        if not products:
            print("No products to process!")
            return

        stats = {'scraped': 0, 'updated': 0, 'not_found': 0, 'errors': 0}

        for i, product in enumerate(products, 1):
            fd = product.get('fieldData', {})
            item_id = product.get('id')
            name = fd.get('name', '')
            slug = fd.get('slug', '')
            brand = self.get_brand_name(fd.get('brand', []))

            print(f"[{i}/{len(products)}] {brand}: {name[:40]}...", end=' ', flush=True)

            content = self.scrape_product(name, slug, brand)

            if content:
                stats['scraped'] += 1
                if self.update_product(item_id, content):
                    stats['updated'] += 1
                    fields = list(content.keys())
                    print(f"✓ ({', '.join(fields)})")
                else:
                    stats['errors'] += 1
                    print("✗ update failed")
            else:
                stats['not_found'] += 1
                print("- not found")

            if i % 20 == 0:
                print(f"\n--- Progress: {i}/{len(products)} | Updated: {stats['updated']} ---\n")

        print(f"\n{'='*50}")
        print("SUMMARY")
        print(f"{'='*50}")
        print(f"Products processed: {len(products)}")
        print(f"Content found: {stats['scraped']}")
        print(f"Updated: {stats['updated']}")
        print(f"Not found: {stats['not_found']}")
        print(f"Errors: {stats['errors']}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, help='Limit products')
    parser.add_argument('--brand', type=str, help='Filter by brand name')
    parser.add_argument('--all', action='store_true', help='Process all')
    args = parser.parse_args()

    limit = args.limit if args.limit else (None if args.all else 30)

    scraper = DrawerContentScraper()
    scraper.run(limit=limit, brand_filter=args.brand)
