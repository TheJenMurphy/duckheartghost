#!/usr/bin/env python3
"""
Simple HTTP-based ingredient scraper.
Works by fetching product pages and extracting ingredients from HTML/JSON.

Usage:
    python scrape_ingredients_simple.py --limit 50
    python scrape_ingredients_simple.py --all
"""

import os
import re
import sys
import time
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

# Brand URL mappings
BRAND_URLS = {
    "Tower 28 Beauty": "https://tower28beauty.com",
    "Tower 28": "https://tower28beauty.com",
    "Kosas Cosmetics": "https://kosas.com",
    "Kosas": "https://kosas.com",
    "ILIA Beauty": "https://iliabeauty.com",
    "ILIA": "https://iliabeauty.com",
    "Saie": "https://saiehello.com",
    "Westman Atelier": "https://westman-atelier.com",
    "RMS Beauty": "https://rmsbeauty.com",
    "Vapour Beauty": "https://vapourbeauty.com",
    "Lawless Beauty": "https://lawlessbeauty.com",
    "Ere Perez": "https://ereperez.com",
    "Beautycounter": "https://beautycounter.com",
    "Tata Harper": "https://tataharperskincare.com",
    "Drunk Elephant": "https://drunkelephant.com",
    "Youth To The People": "https://youthtothepeople.com",
    "Herbivore Botanicals": "https://herbivorebotanicals.com",
    "Biossance": "https://biossance.com",
    "Cocokind": "https://cocokind.com",
    "Osea": "https://oseamalibu.com",
    "OSEA": "https://oseamalibu.com",
    "True Botanicals": "https://truebotanicals.com",
    "Pai Skincare": "https://paiskincare.com",
    "Pai": "https://paiskincare.com",
    "May Lindstrom": "https://maylindstrom.com",
    "Tula Skincare": "https://tula.com",
    "TULA": "https://tula.com",
    "Versed": "https://versedskin.com",
    "Innbeauty Project": "https://innbeauty.com",
    "Kinship": "https://lovekinship.com",
    "Farmacy": "https://farmacybeauty.com",
    "Alpyn Beauty": "https://alpynbeauty.com",
    "Le Prunier": "https://leprunier.com",
    "Agent Nateur": "https://agentnateur.com",
    "AGENT NATEUR": "https://agentnateur.com",
    "Odacité": "https://odacite.com",
    "Odacite": "https://odacite.com",
    "Ren Clean Skincare": "https://usa.renskincare.com",
    "REN": "https://usa.renskincare.com",
    "Josh Rosebrook": "https://joshrosebrook.com",
    "Rahua": "https://rahua.com",
    "Innersense": "https://innersensebeauty.com",
    "Act+Acre": "https://actandacre.com",
    "Crown Affair": "https://crownaffair.com",
    "Olaplex": "https://olaplex.com",
    "Nécessaire": "https://necessaire.com",
    "Necessaire": "https://necessaire.com",
    "Salt & Stone": "https://saltandstone.com",
    "Corpus": "https://corpusnaturals.com",
    "Supergoop!": "https://supergoop.com",
    "Supergoop": "https://supergoop.com",
    "Coola": "https://coola.com",
    "Indie Lee": "https://indielee.com",
    "One/Size": "https://onesize.com",
    "ONE/SIZE": "https://onesize.com",
    "One Size": "https://onesize.com",
    "Merit": "https://meritbeauty.com",
    "MERIT": "https://meritbeauty.com",
    "MERIT beauty": "https://meritbeauty.com",
    "Jones Road Beauty": "https://jonesroadbeauty.com",
    "Jones Road": "https://jonesroadbeauty.com",
    "W3ll People": "https://w3llpeople.com",
    "W3LL PEOPLE": "https://w3llpeople.com",
    "Kjaer Weis": "https://kjaerweis.com",
    "LYS Beauty": "https://lysbeauty.com",
    "LYS": "https://lysbeauty.com",
    "lys BEAUTY": "https://lysbeauty.com",
    "Jillian Dempsey": "https://jilliandempsey.com",
    "Henné Organics": "https://henneorganics.com",
    "Henne Organics": "https://henneorganics.com",
    "True + Luscious": "https://trueandluscious.com",
    "Fitglow Beauty": "https://fitglowbeauty.com",
    "100% Pure": "https://100percentpure.com",
    "Ursa Major": "https://ursamajorvt.com",
    "Prima": "https://prima.co",
    "Dieux Skin": "https://dieuxskin.com",
    "DIEUX": "https://dieuxskin.com",
    "Marie Veronique": "https://marieveronique.com",
    "MARIE VERONIQUE": "https://marieveronique.com",
    "Codex Labs": "https://codexlabs.co",
    "Codex Beauty": "https://codexlabs.co",
    "CODEX LABS": "https://codexlabs.co",
    "Circumference": "https://circumferencenyc.com",
    "CIRCUMFERENCE": "https://circumferencenyc.com",
    "RÓEN": "https://rfroen.com",
    "Roen": "https://rfroen.com",
    "ROEN": "https://rfroen.com",
    "Surratt Beauty": "https://surratt.com",
    "Surratt": "https://surratt.com",
    "SURRATT": "https://surratt.com",
    "Dr. Loretta": "https://drloretta.com",
    "Joanna Vargas": "https://joannavargas.com",
    "VENN Skincare": "https://vennskincare.com",
    "VENN": "https://vennskincare.com",
    "Typology": "https://typology.com",
    "TYPOLOGY": "https://typology.com",
    "Monastery": "https://monasterygoods.com",
    "MONASTERY": "https://monasterygoods.com",
    "MACRENE actives": "https://macreneactives.com",
    "Macrene Actives": "https://macreneactives.com",
    "Skinfix": "https://skinfix.com",
    "SKINFIX": "https://skinfix.com",
    "Grown Alchemist": "https://grownalchemist.com",
    "Finding Ferdinand": "https://findingferdinand.com",
    "Exa": "https://exabeauty.com",
    "Soshe Beauty": "https://soshebeauty.com",
    "Gen See": "https://gensee.co",
    "Mob Beauty": "https://mobbeauty.com",
    "MOB Beauty": "https://mobbeauty.com",
    "Ilia Beauty": "https://iliabeauty.com",
    "Tata Harper Skincare": "https://tataharperskincare.com",
    "Rare Beauty": "https://rarebeauty.com",
    "Rhode Skin": "https://rhodeskin.com",
    "Milk makeup": "https://milkmakeup.com",
    "MILK MAKEUP": "https://milkmakeup.com",
}

# Keywords that indicate non-ingredient items
NON_INGREDIENT_KEYWORDS = [
    'brush', 'sponge', 'bag', 'pouch', 'keychain', 'mirror', 'case', 'holder',
    'tool', 'applicator', 'kit bag', 'travel bag', 'makeup bag', 'book', 'gift card',
    'trucker', 'hat', 'cap', 'tote', 'bundle', 'set', 'duo', 'trio', 'collection',
    'sampler', 'discovery', 'mini set', 'refill', 'sock', 'headband', 'scrunchie',
    'towel', 'cloth', 'wipe', 'zine', 'print', 'consultation', 'gift:', 'free gift',
    'sharpener', 'test -', 'parent item', 'all products', 'lash cluster', 'two-pack',
    'yoga facelift', 'accessing the'
]


class SimpleIngredientScraper:
    """Scrape ingredients using simple HTTP requests."""

    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.webflow_session = requests.Session()
        self.webflow_session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        })
        self._last_webflow_request = 0
        self._brand_cache = {}

        # HTTP session for scraping
        self.http_session = requests.Session()
        self.http_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

        self._load_brands()

    def _load_brands(self):
        """Load brand ID -> name mapping."""
        print("Loading brands...")
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
        print(f"Loaded {len(self._brand_cache)} brands")

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

    def is_accessory(self, name):
        """Check if product is likely an accessory."""
        name_lower = name.lower()
        return any(kw in name_lower for kw in NON_INGREDIENT_KEYWORDS)

    def get_brand_url(self, brand_name):
        """Get brand website URL."""
        if not brand_name:
            return None
        if brand_name in BRAND_URLS:
            return BRAND_URLS[brand_name]
        for key, url in BRAND_URLS.items():
            if key.lower() == brand_name.lower():
                return url
        return None

    def clean_slug(self, slug, brand_name):
        """Clean slug by removing brand prefix and ID suffix."""
        clean = slug
        brand_slug = re.sub(r'[^a-z0-9]', '-', brand_name.lower()).strip('-')
        prefixes = [f"{brand_slug}-", brand_slug.replace('-', '') + '-']
        for prefix in prefixes:
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
                break
        clean = re.sub(r'-[a-f0-9]{5,6}$', '', clean)
        return clean

    def extract_ingredients_from_html(self, html):
        """Extract ingredients from HTML content."""
        if not html:
            return None

        # Method 1: JSON ingredients pattern (most reliable - used by many Shopify sites)
        json_patterns = [
            r'"ingredients"\s*:\s*"([^"]{50,})"',
            r"'ingredients'\s*:\s*'([^']{50,})'",
            r'"product_ingredient[s]?"\s*:\s*"([^"]{50,})"',
        ]
        for pattern in json_patterns:
            match = re.search(pattern, html, re.I)
            if match:
                ingredients = match.group(1).strip()
                if ',' in ingredients and len(ingredients) > 50:
                    # Unescape common escapes
                    ingredients = ingredients.replace('\\u0026', '&')
                    ingredients = ingredients.replace('\\/', '/')
                    ingredients = ingredients.replace('\\n', ' ')
                    ingredients = re.sub(r'\s+', ' ', ingredients)
                    return ingredients[:2000]

        # Method 2: Look for structured data with ingredients
        ld_json_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>([^<]+)</script>'
        for match in re.finditer(ld_json_pattern, html, re.I):
            try:
                import json
                data = json.loads(match.group(1))
                if isinstance(data, dict):
                    ing = data.get('ingredients') or data.get('productIngredients')
                    if ing and isinstance(ing, str) and len(ing) > 50:
                        return ing[:2000]
            except:
                pass

        # Method 3: Look for visible ingredient text patterns
        text_patterns = [
            # Pattern: "Ingredients: Water, Glycerin, ..."
            r'(?:Full\s+)?Ingredients?\s*[:\-]\s*</?\w+[^>]*>\s*([A-Z][^<]{100,500})',
            r'>(?:Full\s+)?Ingredients?\s*[:\-]\s*([A-Z][^<]{100,500})',
        ]
        for pattern in text_patterns:
            match = re.search(pattern, html, re.I)
            if match:
                ingredients = match.group(1).strip()
                # Clean up HTML entities
                ingredients = re.sub(r'&\w+;', ' ', ingredients)
                ingredients = re.sub(r'<[^>]+>', ' ', ingredients)
                ingredients = re.sub(r'\s+', ' ', ingredients)
                if ',' in ingredients and len(ingredients) > 50:
                    return ingredients[:2000]

        return None

    def scrape_product_ingredients(self, product_name, product_slug, brand_name):
        """Scrape ingredients for a single product."""
        brand_url = self.get_brand_url(brand_name)
        if not brand_url:
            return None

        # Try multiple slug variations
        clean = self.clean_slug(product_slug, brand_name)
        name_slug = re.sub(r'[^a-z0-9]+', '-', product_name.lower()).strip('-')
        name_slug = re.sub(r'-+', '-', name_slug)

        slugs_to_try = list(dict.fromkeys([product_slug, clean, name_slug]))  # Unique, preserve order

        for slug in slugs_to_try:
            urls = [
                f"{brand_url}/products/{slug}",
                f"{brand_url}/collections/all/products/{slug}",
            ]
            for url in urls:
                try:
                    resp = self.http_session.get(url, timeout=10, allow_redirects=True)
                    if resp.ok and resp.status_code == 200:
                        # Check if it's a real product page (not 404 soft redirect)
                        if '404' in resp.text[:500].lower() or 'page not found' in resp.text[:500].lower():
                            continue

                        ingredients = self.extract_ingredients_from_html(resp.text)
                        if ingredients:
                            return ingredients
                except requests.RequestException:
                    continue

        return None

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
        print("Fetching products without ingredients...")
        products = self.get_products_without_ingredients(limit=limit)
        print(f"Found {len(products)} products to process\n")

        if not products:
            print("No products to process")
            return

        stats = {
            'scraped': 0,
            'updated': 0,
            'no_brand_url': 0,
            'not_found': 0,
            'errors': 0,
        }

        for i, product in enumerate(products, 1):
            fd = product.get('fieldData', {})
            item_id = product.get('id')
            name = fd.get('name', 'Unknown')
            slug = fd.get('slug', '')
            brand_ref = fd.get('brand', [])

            # Get brand name from reference ID
            brand = ''
            if isinstance(brand_ref, list) and brand_ref:
                brand_id = brand_ref[0]
                brand = self._brand_cache.get(brand_id, '')
            elif isinstance(brand_ref, str):
                brand = self._brand_cache.get(brand_ref, '')

            if not self.get_brand_url(brand):
                stats['no_brand_url'] += 1
                continue

            ingredients = self.scrape_product_ingredients(name, slug, brand)

            if ingredients:
                stats['scraped'] += 1
                ing_html = f"<p>{ingredients}</p>"

                if self.update_product(item_id, ing_html):
                    stats['updated'] += 1
                    print(f"  [{i}/{len(products)}] {name[:40]}: Updated ({len(ingredients)} chars)")
                else:
                    stats['errors'] += 1
                    print(f"  [{i}/{len(products)}] {name[:40]}: Update failed")
            else:
                stats['not_found'] += 1

            if i % 25 == 0:
                print(f"\n  --- Progress: {i}/{len(products)} | Updated: {stats['updated']} ---\n")

        print(f"\n{'='*50}")
        print("SUMMARY")
        print(f"{'='*50}")
        print(f"Products processed: {len(products)}")
        print(f"Ingredients scraped: {stats['scraped']}")
        print(f"Successfully updated: {stats['updated']}")
        print(f"No brand URL: {stats['no_brand_url']}")
        print(f"Not found on site: {stats['not_found']}")
        print(f"Update errors: {stats['errors']}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Scrape missing ingredients with simple HTTP')
    parser.add_argument('--limit', type=int, help='Limit number of products')
    parser.add_argument('--all', action='store_true', help='Process all products')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all products including not found')

    args = parser.parse_args()

    limit = None
    if args.limit:
        limit = args.limit
    elif not args.all:
        limit = 50  # Default

    scraper = SimpleIngredientScraper()
    scraper.run(limit=limit)
