#!/usr/bin/env python3
"""
Scrape ingredients from Credo Beauty for products missing ingredient data.

Usage:
    python scrape_credo_ingredients.py --limit 50
    python scrape_credo_ingredients.py --all
"""

import os
import re
import sys
import time
import requests
from pathlib import Path
from difflib import SequenceMatcher

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
CREDO_BASE = "https://credobeauty.com"

# Brand name to Credo collection slug mapping
BRAND_TO_CREDO = {
    "Mob Beauty": "mob-beauty",
    "MOB Beauty": "mob-beauty",
    "Gen See": "gen-see",
    "GEN SEE": "gen-see",
    "Soshe Beauty": "soshe-beauty",
    "SOSHE Beauty": "soshe-beauty",
    "Tata Harper": "tata-harper",
    "Tata Harper Skincare": "tata-harper",
    "Westman Atelier": "westman-atelier",
    "Tower 28 Beauty": "tower-28",
    "Tower 28": "tower-28",
    "Kosas": "kosas",
    "Kosas Cosmetics": "kosas",
    "RMS Beauty": "rms-beauty",
    "Necessaire": "necessaire",
    "Nécessaire": "necessaire",
    "True Botanicals": "true-botanicals",
    "Osea": "osea",
    "OSEA": "osea",
    "Indie Lee": "indie-lee",
    "Grown Alchemist": "grown-alchemist",
    "LYS Beauty": "lys-beauty",
    "lys BEAUTY": "lys-beauty",
    "Ursa Major": "ursa-major",
    "Jillian Dempsey": "jillian-dempsey",
    "ILIA Beauty": "ilia",
    "ILIA": "ilia",
    "Saie": "saie",
    "Merit": "merit",
    "MERIT": "merit",
    "Lawless Beauty": "lawless",
    "Biossance": "biossance",
    "Drunk Elephant": "drunk-elephant",
    "Youth To The People": "youth-to-the-people",
    "Herbivore Botanicals": "herbivore",
    "Cocokind": "cocokind",
    "Farmacy": "farmacy",
    "Alpyn Beauty": "alpyn-beauty",
    "Pai Skincare": "pai-skincare",
    "Pai": "pai-skincare",
    "Versed": "versed",
    "Kinship": "kinship",
    "Coola": "coola",
    "Supergoop!": "supergoop",
    "Supergoop": "supergoop",
    "Fitglow Beauty": "fitglow-beauty",
    "100% Pure": "100-pure",
    "Ere Perez": "ere-perez",
    "Vapour Beauty": "vapour",
    "Kjaer Weis": "kjaer-weis",
    "W3ll People": "w3ll-people",
    "W3LL PEOPLE": "w3ll-people",
    "Jones Road Beauty": "jones-road",
    "Jones Road": "jones-road",
    "Agent Nateur": "agent-nateur",
    "AGENT NATEUR": "agent-nateur",
    "Odacité": "odacite",
    "Odacite": "odacite",
    "Josh Rosebrook": "josh-rosebrook",
    "Rahua": "rahua",
    "Innersense": "innersense",
    "Act+Acre": "act-acre",
    "Crown Affair": "crown-affair",
    "Salt & Stone": "salt-stone",
    "Henné Organics": "henne-organics",
    "Henne Organics": "henne-organics",
}

# Non-ingredient items to skip
# True accessories without ingredients (tools, bags, etc.)
NON_INGREDIENT_KEYWORDS = [
    'brush', 'sponge', 'bag', 'pouch', 'keychain', 'mirror', 'case', 'holder',
    'tool', 'applicator', 'kit bag', 'travel bag', 'makeup bag', 'book', 'gift card',
    'trucker', 'hat', 'cap', 'tote', 'sock', 'headband', 'scrunchie', 'hair clip',
    'towel', 'cloth', 'wipe', 'sharpener', 'sweatshirt', 'roller'
]
# Note: Sets/bundles/duos DO have ingredients (combined from all products)


class CredoIngredientScraper:
    """Scrape ingredients from Credo Beauty."""

    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.webflow_session = requests.Session()
        self.webflow_session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        })
        self._last_webflow_request = 0
        self._brand_cache = {}

        # HTTP session for Credo
        self.http_session = requests.Session()
        self.http_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })

        # Cache of Credo products by brand
        self._credo_cache = {}

        self._load_brands()

    def _load_brands(self):
        """Load brand ID -> name mapping."""
        print("Loading brands from Webflow...")
        offset = 0
        while True:
            result = self._webflow_request('GET',
                f'/collections/{BRANDS_COLLECTION_ID}/items?limit=100&offset={offset}')
            if not result:
                break
            items = result.get('items', [])
            if not items:
                break
            for item in items:
                fd = item.get('fieldData', {})
                self._brand_cache[item.get('id')] = fd.get('name', '')
            offset += 100
            if len(items) < 100:
                break
        print(f"  Loaded {len(self._brand_cache)} brands")

    def _webflow_rate_limit(self):
        elapsed = time.time() - self._last_webflow_request
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_webflow_request = time.time()

    def _webflow_request(self, method, endpoint, data=None):
        self._webflow_rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'
        try:
            if method == 'GET':
                resp = self.webflow_session.get(url)
            elif method == 'PATCH':
                resp = self.webflow_session.patch(url, json=data)
            else:
                return None
            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 60))
                print(f'Rate limited. Waiting {wait}s...')
                time.sleep(wait)
                return self._webflow_request(method, endpoint, data)
            if not resp.ok:
                return None
            return resp.json() if resp.text else {}
        except requests.RequestException:
            return None

    def get_credo_collection_slug(self, brand_name):
        """Get Credo collection slug for a brand."""
        if not brand_name:
            return None
        if brand_name in BRAND_TO_CREDO:
            return BRAND_TO_CREDO[brand_name]
        # Try case-insensitive match
        for key, slug in BRAND_TO_CREDO.items():
            if key.lower() == brand_name.lower():
                return slug
        return None

    def load_credo_products(self, credo_slug):
        """Load all products from a Credo brand collection."""
        if credo_slug in self._credo_cache:
            return self._credo_cache[credo_slug]

        products = {}
        url = f"{CREDO_BASE}/collections/{credo_slug}"

        try:
            resp = self.http_session.get(url, timeout=20)
            if not resp.ok:
                self._credo_cache[credo_slug] = products
                return products

            # Find all product links
            links = re.findall(r'href="/products/([^"?#]+)"', resp.text)
            unique_slugs = list(dict.fromkeys(links))

            # Get product titles too
            # Look for product cards with titles
            for slug in unique_slugs:
                if slug == 'giftcard':
                    continue
                products[slug] = {
                    'slug': slug,
                    'url': f"{CREDO_BASE}/products/{slug}",
                    'title_normalized': self.normalize_title(slug.replace('-', ' '))
                }

            self._credo_cache[credo_slug] = products

        except requests.RequestException:
            self._credo_cache[credo_slug] = products

        return products

    def normalize_title(self, title):
        """Normalize a product title for matching."""
        # Remove brand name, lowercase, remove special chars
        title = title.lower()
        title = re.sub(r'[^a-z0-9\s]', '', title)
        title = re.sub(r'\s+', ' ', title).strip()
        return title

    def find_credo_match(self, product_name, brand_name, credo_products):
        """Find the best matching Credo product for a Webflow product."""
        if not credo_products:
            return None

        # Normalize the product name
        norm_name = self.normalize_title(product_name)

        # Also try without brand prefix
        brand_lower = brand_name.lower() if brand_name else ''
        norm_no_brand = norm_name
        for prefix in [brand_lower, brand_lower.replace(' ', '')]:
            if norm_no_brand.startswith(prefix):
                norm_no_brand = norm_no_brand[len(prefix):].strip()

        best_match = None
        best_score = 0.0

        for slug, info in credo_products.items():
            credo_norm = info['title_normalized']

            # Try different matching strategies
            scores = [
                SequenceMatcher(None, norm_name, credo_norm).ratio(),
                SequenceMatcher(None, norm_no_brand, credo_norm).ratio(),
            ]

            # Also check if key words match
            name_words = set(norm_name.split())
            credo_words = set(credo_norm.split())
            if name_words and credo_words:
                word_overlap = len(name_words & credo_words) / max(len(name_words), len(credo_words))
                scores.append(word_overlap)

            score = max(scores)
            if score > best_score:
                best_score = score
                best_match = info

        # Require minimum match threshold
        if best_score >= 0.5:
            return best_match
        return None

    def extract_ingredients(self, credo_url):
        """Extract ingredients from a Credo product page."""
        try:
            resp = self.http_session.get(credo_url, timeout=15)
            if not resp.ok:
                return None

            html = resp.text

            # Look for ingredients-p class
            match = re.search(r'class="[^"]*ingredients-p[^"]*"[^>]*>([^<]+)', html)
            if match:
                ingredients = match.group(1).strip()
                if len(ingredients) > 30:
                    # Clean up HTML entities and formatting
                    ingredients = self.clean_ingredients(ingredients)
                    return ingredients

            return None
        except requests.RequestException:
            return None

    def clean_ingredients(self, text):
        """Clean up ingredient text."""
        # Decode HTML entities
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&amp;', '&').replace('&nbsp;', ' ')
        text = re.sub(r'&[a-z]+;', ' ', text)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove prefix like "Product Name: Ingredients:"
        text = re.sub(r'^[^:]+:\s*Ingredients:\s*', '', text, flags=re.I)
        text = re.sub(r'^Ingredients:\s*', '', text, flags=re.I)

        # Replace || separators with commas
        text = text.replace(' || ', ', ')

        return text[:2000]  # Limit length

    def is_accessory(self, name):
        """Check if product is likely an accessory."""
        name_lower = name.lower()
        return any(kw in name_lower for kw in NON_INGREDIENT_KEYWORDS)

    def get_products_without_ingredients(self, limit=None):
        """Get products that need ingredients."""
        products = []
        offset = 0
        batch_limit = 100

        while True:
            result = self._webflow_request('GET',
                f'/collections/{PRODUCTS_COLLECTION_ID}/items?limit={batch_limit}&offset={offset}')
            if not result:
                break
            items = result.get('items', [])
            if not items:
                break

            for item in items:
                fd = item.get('fieldData', {})
                ing = fd.get('ingredients-2', '') or ''
                name = fd.get('name', '')

                if ing.strip() and len(ing.strip()) > 20:
                    continue
                if self.is_accessory(name):
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

    def update_product(self, item_id, ingredients_html):
        """Update product with ingredients."""
        update_data = {
            'fieldData': {
                'ingredients-2': ingredients_html
            }
        }
        result = self._webflow_request('PATCH',
            f'/collections/{PRODUCTS_COLLECTION_ID}/items/{item_id}',
            update_data)
        return result is not None

    def run(self, limit=None):
        """Run the ingredient scraping process."""
        print("\nFetching products without ingredients...")
        products = self.get_products_without_ingredients(limit=limit)
        print(f"Found {len(products)} products to process\n")

        if not products:
            print("No products to process")
            return

        # Group by brand
        by_brand = {}
        for product in products:
            fd = product.get('fieldData', {})
            brand_ref = fd.get('brand', [])
            brand = ''
            if isinstance(brand_ref, list) and brand_ref:
                brand = self._brand_cache.get(brand_ref[0], '')
            elif isinstance(brand_ref, str):
                brand = self._brand_cache.get(brand_ref, '')

            if brand not in by_brand:
                by_brand[brand] = []
            by_brand[brand].append(product)

        print(f"Products grouped into {len(by_brand)} brands\n")

        stats = {
            'processed': 0,
            'matched': 0,
            'updated': 0,
            'no_credo': 0,
            'no_match': 0,
            'no_ingredients': 0,
            'errors': 0,
        }

        for brand, brand_products in by_brand.items():
            credo_slug = self.get_credo_collection_slug(brand)

            if not credo_slug:
                stats['no_credo'] += len(brand_products)
                continue

            # Load Credo products for this brand
            credo_products = self.load_credo_products(credo_slug)
            if not credo_products:
                print(f"  {brand}: No products found on Credo")
                stats['no_credo'] += len(brand_products)
                continue

            print(f"\n{brand} ({len(brand_products)} products, {len(credo_products)} on Credo):")

            for product in brand_products:
                fd = product.get('fieldData', {})
                item_id = product.get('id')
                name = fd.get('name', 'Unknown')
                stats['processed'] += 1

                # Find matching Credo product
                match = self.find_credo_match(name, brand, credo_products)

                if not match:
                    stats['no_match'] += 1
                    continue

                stats['matched'] += 1

                # Extract ingredients
                ingredients = self.extract_ingredients(match['url'])

                if not ingredients:
                    stats['no_ingredients'] += 1
                    continue

                # Update Webflow
                ing_html = f"<p>{ingredients}</p>"
                if self.update_product(item_id, ing_html):
                    stats['updated'] += 1
                    print(f"  ✓ {name[:40]}: Updated ({len(ingredients)} chars)")
                else:
                    stats['errors'] += 1
                    print(f"  ✗ {name[:40]}: Update failed")

                # Small delay to be nice to Credo
                time.sleep(0.3)

        print(f"\n{'='*50}")
        print("SUMMARY")
        print(f"{'='*50}")
        print(f"Products processed: {stats['processed']}")
        print(f"Matched on Credo: {stats['matched']}")
        print(f"Successfully updated: {stats['updated']}")
        print(f"No Credo collection: {stats['no_credo']}")
        print(f"No match found: {stats['no_match']}")
        print(f"No ingredients on page: {stats['no_ingredients']}")
        print(f"Update errors: {stats['errors']}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Scrape ingredients from Credo Beauty')
    parser.add_argument('--limit', type=int, help='Limit number of products')
    parser.add_argument('--all', action='store_true', help='Process all products')

    args = parser.parse_args()

    limit = None
    if args.limit:
        limit = args.limit
    elif not args.all:
        limit = 50  # Default

    scraper = CredoIngredientScraper()
    scraper.run(limit=limit)
