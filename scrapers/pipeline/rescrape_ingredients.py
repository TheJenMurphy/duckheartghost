#!/usr/bin/env python3
"""
Re-scrape products for ingredients.

Reconstructs product URLs from brand + slug and scrapes for ingredients,
then updates Webflow with the extracted ingredient data.

Usage:
    python rescrape_ingredients.py --brand "Tower 28 Beauty" --limit 10
    python rescrape_ingredients.py --all --limit 50
    python rescrape_ingredients.py --brand "Kosas Cosmetics" --all
"""

import os
import re
import sys
import time
import json
from pathlib import Path
from urllib.parse import urlparse

# Load .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import requests
from bs4 import BeautifulSoup

# Import the improved ingredient extraction
from pipeline import extract_ingredients

# Webflow API
WEBFLOW_API_BASE = "https://api.webflow.com/v2"
PRODUCTS_COLLECTION_ID = "67b260cb70f3225a0a29e7e2"

# Brand name -> website URL mapping
# These are Shopify stores, URLs follow pattern: website.com/products/slug
BRAND_URLS = {
    # Major clean beauty brands
    "Tower 28 Beauty": "https://tower28beauty.com",
    "Kosas Cosmetics": "https://kosas.com",
    "ILIA Beauty": "https://iliabeauty.com",
    "RMS Beauty": "https://rmsbeauty.com",
    "MERIT Beauty": "https://meritbeauty.com",
    "Rare Beauty": "https://rarebeauty.com",
    "Milk Makeup": "https://milkmakeup.com",
    "rhode": "https://rhodeskin.com",
    "Indie Lee": "https://indielee.com",
    "Tata Harper Skincare": "https://tataharperskincare.com",
    "Tata Harper": "https://tataharperskincare.com",
    "True Botanicals": "https://truebotanicals.com",
    "Marie Veronique": "https://marieveronique.com",
    "Ursa Major Skincare": "https://ursamajorvt.com",
    "Ursa Major": "https://ursamajorvt.com",
    "Ursa_Major": "https://ursamajorvt.com",
    "Westman Atelier": "https://westman-atelier.com",
    "Westman-Atelier": "https://westman-atelier.com",
    "LYS Beauty": "https://lysbeauty.com",
    "SOSHE Beauty": "https://soshebeauty.com",
    "Finding Ferdinand": "https://findingferdinand.com",
    "Mob Beauty": "https://mobbeauty.com",
    "MOB Beauty": "https://mobbeauty.com",
    "Beautycounter": "https://beautycounter.com",
    "Credo Beauty": "https://credobeauty.com",
    "Follain": "https://follain.com",
    "Cocokind": "https://cocokind.com",
    "Youth to the People": "https://youthtothepeople.com",
    "Herbivore Botanicals": "https://herbivorebotanicals.com",
    "Osea": "https://oseamalibu.com",
    "Biossance": "https://biossance.com",
    "Drunk Elephant": "https://drunkelephant.com",
    "Tatcha": "https://tatcha.com",
    "Saie": "https://saiehello.com",
    "Jones Road Beauty": "https://jonesroadbeauty.com",
    "Vapour Beauty": "https://vapourbeauty.com",
    "W3ll People": "https://w3llpeople.com",
    "Juice Beauty": "https://juicebeauty.com",
    "100% Pure": "https://100percentpure.com",
    "Pai Skincare": "https://paiskincare.us",
    "Grown Alchemist": "https://grownalchemist.com",
    "Jillian Dempsey": "https://jilliandempsey.com",
    "Gen See": "https://gensee.co",
    "Exa Beauty": "https://exabeauty.com",
    "Sunnies Face": "https://sunniesface.com",
    "Lawless Beauty": "https://lawlessbeauty.com",
    "Ami Cole": "https://amicole.com",
    "Tower28": "https://tower28beauty.com",
    "Kosas": "https://kosas.com",
    "ILIA": "https://iliabeauty.com",
    "RMS": "https://rmsbeauty.com",
    "MERIT": "https://meritbeauty.com",
}


class IngredientRescraper:
    """Re-scrape products for ingredients."""

    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

        self.scrape_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        self._last_request = 0

    def _rate_limit(self, delay=0.5):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request = time.time()

    def _api_request(self, method, endpoint, data=None):
        """Make Webflow API request."""
        self._rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'

        try:
            if method == 'GET':
                resp = self.session.get(url)
            elif method == 'PATCH':
                resp = self.session.patch(url, json=data)
            else:
                return None

            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 60))
                print(f'Rate limited. Waiting {wait}s...')
                time.sleep(wait)
                return self._api_request(method, endpoint, data)

            if not resp.ok:
                print(f'API Error {resp.status_code}: {resp.text[:200]}')
                return None

            return resp.json() if resp.text else {}

        except requests.RequestException as e:
            print(f'Request error: {e}')
            return None

    def get_brand_url(self, brand_name):
        """Get website URL for a brand."""
        # Try exact match
        if brand_name in BRAND_URLS:
            return BRAND_URLS[brand_name]

        # Try case-insensitive match
        brand_lower = brand_name.lower()
        for name, url in BRAND_URLS.items():
            if name.lower() == brand_lower:
                return url

        # Try partial match
        for name, url in BRAND_URLS.items():
            if brand_lower in name.lower() or name.lower() in brand_lower:
                return url

        return None

    def construct_product_url(self, brand_name, product_slug):
        """Construct product URL from brand and slug."""
        brand_url = self.get_brand_url(brand_name)
        if not brand_url:
            return None

        # Extract just the product part of the slug
        # Slugs are like "tower-28-beauty-sunnydays-tinted-spf"
        # We need just "sunnydays-tinted-spf"

        # Try to remove brand prefix from slug
        brand_slug = re.sub(r'[^a-z0-9]+', '-', brand_name.lower()).strip('-')

        product_part = product_slug
        if product_slug.startswith(brand_slug):
            product_part = product_slug[len(brand_slug):].lstrip('-')

        # Also try removing common brand variations
        brand_variations = [
            brand_slug,
            brand_slug.replace('-beauty', ''),
            brand_slug.replace('-cosmetics', ''),
            brand_slug.replace('-skincare', ''),
        ]

        for var in brand_variations:
            if product_slug.startswith(var + '-'):
                product_part = product_slug[len(var)+1:]
                break

        # Remove any random suffix (like -0b6d9)
        product_part = re.sub(r'-[a-f0-9]{5}$', '', product_part)

        return f"{brand_url}/products/{product_part}"

    def scrape_ingredients(self, url):
        """Scrape ingredients from a product URL."""
        try:
            resp = requests.get(url, headers=self.scrape_headers, timeout=15)
            if resp.status_code != 200:
                return None

            # Use the improved ingredient extraction
            ingredients = extract_ingredients(resp.text, url, self.scrape_headers)
            return ingredients if ingredients else None

        except Exception as e:
            return None

    def get_products(self, brand_filter=None, limit=None, skip_with_ingredients=True):
        """Get products from Webflow."""
        products = []
        offset = 0
        batch_limit = 100

        while True:
            endpoint = f'/collections/{PRODUCTS_COLLECTION_ID}/items?limit={batch_limit}&offset={offset}'
            result = self._api_request('GET', endpoint)

            if not result:
                break

            items = result.get('items', [])
            if not items:
                break

            for item in items:
                fd = item.get('fieldData', {})
                brand = fd.get('brand-name-2', '')

                # Filter by brand if specified
                if brand_filter and brand.lower() != brand_filter.lower():
                    continue

                # Skip if already has ingredients (optional)
                if skip_with_ingredients and fd.get('ingredients-2'):
                    continue

                products.append(item)

            offset += batch_limit

            if len(items) < batch_limit:
                break

            if limit and len(products) >= limit:
                break

        if limit:
            products = products[:limit]

        return products

    def update_product_ingredients(self, item_id, ingredients):
        """Update product with ingredients."""
        update_data = {
            'fieldData': {
                'ingredients-2': f'<p>{ingredients}</p>'
            }
        }

        result = self._api_request('PATCH',
            f'/collections/{PRODUCTS_COLLECTION_ID}/items/{item_id}',
            update_data)

        return result is not None

    def run(self, brand_filter=None, limit=None, skip_with_ingredients=True):
        """Run the re-scraping process."""
        print(f"Fetching products...")
        if brand_filter:
            print(f"  Filtering by brand: {brand_filter}")

        products = self.get_products(
            brand_filter=brand_filter,
            limit=limit,
            skip_with_ingredients=skip_with_ingredients
        )

        print(f"Found {len(products)} products to process")

        if not products:
            print("No products to process")
            return

        stats = {
            'scraped': 0,
            'updated': 0,
            'no_url': 0,
            'scrape_failed': 0,
            'no_ingredients': 0,
            'update_failed': 0,
        }

        print(f"\nRe-scraping products...\n")

        for i, product in enumerate(products, 1):
            fd = product.get('fieldData', {})
            item_id = product.get('id')
            name = fd.get('name', 'Unknown')[:40]
            brand = fd.get('brand-name-2', 'Unknown')
            slug = fd.get('slug', '')

            # Construct URL
            url = self.construct_product_url(brand, slug)

            if not url:
                stats['no_url'] += 1
                print(f"  [{i}/{len(products)}] {name}: No URL for brand '{brand}'")
                continue

            # Scrape
            print(f"  [{i}/{len(products)}] {name}: Scraping...", end=" ", flush=True)

            # Add delay between scrapes to be respectful
            time.sleep(1)

            ingredients = self.scrape_ingredients(url)
            stats['scraped'] += 1

            if not ingredients:
                stats['no_ingredients'] += 1
                print("No ingredients found")
                continue

            # Update
            success = self.update_product_ingredients(item_id, ingredients)

            if success:
                stats['updated'] += 1
                print(f"Updated ({len(ingredients)} chars)")
            else:
                stats['update_failed'] += 1
                print("Update failed")

            # Progress update
            if i % 20 == 0:
                print(f"\n  --- Progress: {i}/{len(products)} | Updated: {stats['updated']} ---\n")

        # Summary
        print(f"\n{'='*50}")
        print("SUMMARY")
        print(f"{'='*50}")
        print(f"Products processed: {len(products)}")
        print(f"URLs constructed: {stats['scraped']}")
        print(f"No brand URL mapping: {stats['no_url']}")
        print(f"Successfully updated: {stats['updated']}")
        print(f"No ingredients found: {stats['no_ingredients']}")
        print(f"Update failed: {stats['update_failed']}")


def list_brands():
    """List all brands and their URL mappings."""
    print("Configured brand URL mappings:")
    print("-" * 60)
    for brand, url in sorted(BRAND_URLS.items()):
        print(f"  {brand}: {url}")
    print(f"\nTotal: {len(BRAND_URLS)} brands configured")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Re-scrape products for ingredients')
    parser.add_argument('--brand', type=str, help='Filter by brand name')
    parser.add_argument('--limit', type=int, help='Limit number of products')
    parser.add_argument('--all', action='store_true', help='Process all products (no limit)')
    parser.add_argument('--include-existing', action='store_true',
                        help='Include products that already have ingredients')
    parser.add_argument('--list-brands', action='store_true', help='List configured brand URLs')

    args = parser.parse_args()

    if args.list_brands:
        list_brands()
        sys.exit(0)

    limit = None
    if args.limit:
        limit = args.limit
    elif not args.all:
        limit = 10  # Default to 10 for safety

    rescraper = IngredientRescraper()
    rescraper.run(
        brand_filter=args.brand,
        limit=limit,
        skip_with_ingredients=not args.include_existing
    )
