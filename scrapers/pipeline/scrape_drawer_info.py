#!/usr/bin/env python3
"""
Scrape drawer info (ingredients) for products using multiple sources.
Tries brand websites first, then Credo Beauty as fallback.

Usage:
    python scrape_drawer_info.py --limit 50
    python scrape_drawer_info.py --all
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
BRAND_WEBSITES = {
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

# Accessory keywords - these products don't have ingredients
ACCESSORIES = [
    'brush', 'sponge', 'bag', 'pouch', 'keychain', 'mirror', 'case', 'holder',
    'tool', 'applicator', 'kit bag', 'travel bag', 'makeup bag', 'book', 'gift card',
    'trucker', 'hat', 'cap', 'tote', 'bundle', 'set only', 'duo only', 'trio only',
    'sampler', 'discovery set', 'mini set', 'sock', 'headband', 'scrunchie',
    'towel', 'cloth', 'wipe', 'zine', 'print', 'consultation', 'gift:', 'free gift',
    'sharpener', 'test -', 'parent item', 'all products', 'lash cluster', 'two-pack',
    'charm', 'build your', 'edition box', 'stone', 'bandana', 'wristlet',
]


class DrawerInfoScraper:
    """Scrape ingredients from brand websites."""

    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.webflow = requests.Session()
        self.webflow.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        })

        self.http = requests.Session()
        self.http.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
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
            if elapsed < 2.0:  # Be nice to brand sites
                time.sleep(2.0 - elapsed)
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

    def extract_ingredients(self, html):
        """Extract ingredients from HTML."""
        if not html:
            return None

        # Method 1: JSON data with ingredients field
        patterns = [
            r'"ingredients"\s*:\s*"([^"]{50,})"',
            r'"product_ingredients"\s*:\s*"([^"]{50,})"',
            r'"ingredientsList"\s*:\s*"([^"]{50,})"',
        ]
        for p in patterns:
            m = re.search(p, html, re.I)
            if m:
                ing = m.group(1)
                ing = ing.replace('\\u0026', '&').replace('\\/', '/').replace('\\n', ' ')
                ing = re.sub(r'\\u[0-9a-fA-F]{4}', '', ing)
                ing = re.sub(r'\s+', ' ', ing).strip()
                if ',' in ing and len(ing) > 50:
                    return ing[:2000]

        # Method 2: HTML with ingredients section
        html_patterns = [
            r'<(?:div|section|p)[^>]*class="[^"]*ingredient[^"]*"[^>]*>([^<]{50,})</(?:div|section|p)>',
            r'>(?:Full\s+)?Ingredients?\s*[:\-]?\s*</?\w+[^>]*>\s*([A-Z][^<]{100,}?)<',
            r'<p>(?:Full\s+)?Ingredients?\s*[:\-]?\s*([A-Z][^<]{100,}?)</p>',
        ]
        for p in html_patterns:
            m = re.search(p, html, re.I | re.DOTALL)
            if m:
                ing = m.group(1)
                ing = re.sub(r'<[^>]+>', ' ', ing)
                ing = re.sub(r'&\w+;', ' ', ing)
                ing = re.sub(r'\s+', ' ', ing).strip()
                if ',' in ing and len(ing) > 50:
                    return ing[:2000]

        return None

    def scrape_brand_site(self, product_name, product_slug, brand_name):
        """Try to scrape from brand website."""
        domain = BRAND_WEBSITES.get(brand_name)
        if not domain:
            return None

        # Build possible URLs
        name_slug = self.make_slug(product_name)

        # Clean the webflow slug (remove brand prefix and ID suffix)
        clean_slug = product_slug
        brand_slug = self.make_slug(brand_name)
        if clean_slug.startswith(brand_slug + '-'):
            clean_slug = clean_slug[len(brand_slug)+1:]
        clean_slug = re.sub(r'-[a-f0-9]{5,6}$', '', clean_slug)

        slugs = list(dict.fromkeys([clean_slug, name_slug, product_slug]))

        for slug in slugs:
            url = f'https://www.{domain}/products/{slug}'
            try:
                self._rate_limit('http')
                resp = self.http.get(url, timeout=15, allow_redirects=True)
                if resp.ok and '404' not in resp.text[:500].lower():
                    ing = self.extract_ingredients(resp.text)
                    if ing:
                        return ing
            except:
                pass

            # Try without www
            url = f'https://{domain}/products/{slug}'
            try:
                self._rate_limit('http')
                resp = self.http.get(url, timeout=15, allow_redirects=True)
                if resp.ok and '404' not in resp.text[:500].lower():
                    ing = self.extract_ingredients(resp.text)
                    if ing:
                        return ing
            except:
                pass

        return None

    def get_products_missing_ingredients(self, limit=None):
        """Get products needing ingredients."""
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
                ing = fd.get('ingredients-2', '') or ''
                name = fd.get('name', '')

                # Skip if has ingredients or is accessory
                if ing.strip() and len(ing.strip()) > 20:
                    continue
                if self.is_accessory(name):
                    continue

                products.append(item)

            offset += 100
            if len(items) < 100:
                break
            if limit and len(products) >= limit:
                break

        return products[:limit] if limit else products

    def update_product(self, item_id, ingredients):
        """Update product with ingredients."""
        self._rate_limit('webflow')
        resp = self.webflow.patch(
            f'{WEBFLOW_API_BASE}/collections/{PRODUCTS_COLLECTION_ID}/items/{item_id}',
            json={'fieldData': {'ingredients-2': f'<p>{ingredients}</p>'}}
        )
        return resp.ok

    def run(self, limit=None):
        print("\nFetching products missing ingredients...")
        products = self.get_products_missing_ingredients(limit)
        print(f"Found {len(products)} products to process\n")

        if not products:
            print("No products to process!")
            return

        stats = {'scraped': 0, 'updated': 0, 'not_found': 0, 'no_brand': 0}

        for i, product in enumerate(products, 1):
            fd = product.get('fieldData', {})
            item_id = product.get('id')
            name = fd.get('name', '')
            slug = fd.get('slug', '')
            brand = self.get_brand_name(fd.get('brand', []))

            if brand not in BRAND_WEBSITES:
                stats['no_brand'] += 1
                continue

            print(f"[{i}/{len(products)}] {brand}: {name[:40]}...", end=' ')

            ingredients = self.scrape_brand_site(name, slug, brand)

            if ingredients:
                stats['scraped'] += 1
                if self.update_product(item_id, ingredients):
                    stats['updated'] += 1
                    print(f"✓ ({len(ingredients)} chars)")
                else:
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
        print(f"Ingredients found: {stats['scraped']}")
        print(f"Updated: {stats['updated']}")
        print(f"Not found: {stats['not_found']}")
        print(f"No brand mapping: {stats['no_brand']}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, help='Limit products')
    parser.add_argument('--all', action='store_true', help='Process all')
    args = parser.parse_args()

    limit = args.limit if args.limit else (None if args.all else 20)

    scraper = DrawerInfoScraper()
    scraper.run(limit=limit)
