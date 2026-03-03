#!/usr/bin/env python3
"""
Scrape ingredients using headless browser (Playwright) for JS-rendered sites.

Usage:
    python scrape_ingredients_headless.py --collection makeups --limit 50
    python scrape_ingredients_headless.py --collection skincares --all
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

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# APIs
WEBFLOW_API_BASE = "https://api.webflow.com/v2"

# Collection IDs
COLLECTIONS = {
    "makeups": {
        "id": "697d3803e654519eef084068",
        "ingredients_field": "ingredients-2",
    },
    "skincares": {
        "id": "697d723c3df8451b1f1cce1a",
        "ingredients_field": "ingredients-raw",
    },
}
BRANDS_COLLECTION_ID = "697d7df8e654519eef089e6d"

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


class HeadlessIngredientScraper:
    """Scrape ingredients using headless browser."""

    def __init__(self, collection_name="makeups"):
        self.collection_name = collection_name
        self.collection_config = COLLECTIONS.get(collection_name)
        if not self.collection_config:
            raise ValueError(f"Unknown collection: {collection_name}")

        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.webflow_session = requests.Session()
        self.webflow_session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        })
        self._last_webflow_request = 0
        self._brand_cache = {}
        self._load_brands()

        # Playwright browser
        self.playwright = None
        self.browser = None
        self.context = None

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

    def start_browser(self):
        """Start Playwright browser."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

    def stop_browser(self):
        """Stop Playwright browser."""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

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

    def extract_ingredients_from_page(self, page):
        """Extract ingredients from a rendered page."""
        try:
            page.wait_for_load_state('domcontentloaded', timeout=10000)
            time.sleep(2)  # Wait for JS to render
        except PlaywrightTimeout:
            pass

        # Get both HTML and text content
        html = page.content()
        text = page.inner_text('body')

        # Method 1: Look for ingredients in page JSON/data (most reliable)
        json_patterns = [
            r'"ingredients"[:\s]*"([^"]{50,})"',
            r"'ingredients'[:\s]*'([^']{50,})'",
            r'ingredients["\']?\s*:\s*["\']([A-Z][^"\']{50,})["\']',
        ]
        for pattern in json_patterns:
            match = re.search(pattern, html, re.I)
            if match:
                ingredients = match.group(1).strip()
                # Validate - should look like ingredient list
                if ',' in ingredients and len(ingredients) > 50:
                    # Unescape HTML entities
                    ingredients = ingredients.replace('\\u0026', '&').replace('\\/', '/')
                    return ingredients[:2000]

        # Method 2: Try clicking accordions to reveal ingredients
        try:
            accordion_texts = ['Full Ingredients', 'Ingredients', 'Benefits & Ingredients']
            for btn_text in accordion_texts:
                try:
                    btn = page.locator(f'button:has-text("{btn_text}")').first
                    if btn.is_visible():
                        btn.click()
                        time.sleep(0.5)
                except:
                    continue
            # Re-get text after clicking
            text = page.inner_text('body')
        except:
            pass

        # Method 3: Look for ingredient patterns in visible text
        text_patterns = [
            r'(?:Full\s+)?Ingredients?[:\s]*\n*([A-Z][a-zA-Z0-9\s,\(\)\-\.\/\*]+(?:,\s*[A-Za-z0-9\s\(\)\-\.\/\*]+){5,})',
            r'>([Ww]ater[,\s][A-Za-z0-9\s,\(\)\-\.\/\*]+(?:,\s*[A-Za-z0-9\s\(\)\-\.\/\*]+){8,})',
        ]
        for pattern in text_patterns:
            match = re.search(pattern, text)
            if match:
                ingredients = match.group(1).strip()
                ingredients = re.sub(r'\s+', ' ', ingredients)
                if ',' in ingredients and len(ingredients) > 50:
                    return ingredients[:2000]

        # Method 4: Look for ingredient container elements
        ingredient_selectors = [
            '.ingredients-list',
            '.product-ingredients',
            '[data-ingredients]',
            '.ingredient-list',
            '#ingredients',
            '.pdp-ingredients',
            '[class*="ingredient"]',
        ]
        for selector in ingredient_selectors:
            try:
                elem = page.locator(selector).first
                if elem.is_visible():
                    elem_text = elem.inner_text()
                    if len(elem_text) > 50 and ',' in elem_text:
                        return elem_text[:2000]
            except:
                continue

        return None

    def clean_slug(self, slug, brand_name):
        """Clean slug by removing brand prefix and ID suffix."""
        clean = slug
        # Remove common brand prefixes
        brand_slug = re.sub(r'[^a-z0-9]', '-', brand_name.lower()).strip('-')
        prefixes = [f"{brand_slug}-", brand_slug.replace('-', '') + '-']
        for prefix in prefixes:
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
                break
        # Remove ID suffix (5-6 hex chars at end)
        clean = re.sub(r'-[a-f0-9]{5,6}$', '', clean)
        return clean

    def scrape_product_ingredients(self, product_name, product_slug, brand_name):
        """Scrape ingredients for a single product using headless browser."""
        brand_url = self.get_brand_url(brand_name)
        if not brand_url:
            return None

        # Try multiple slug variations
        clean = self.clean_slug(product_slug, brand_name)
        slugs_to_try = [product_slug, clean]

        # Also try creating slug from product name
        name_slug = re.sub(r'[^a-z0-9]+', '-', product_name.lower()).strip('-')
        name_slug = re.sub(r'-+', '-', name_slug)
        if name_slug not in slugs_to_try:
            slugs_to_try.append(name_slug)

        try:
            page = self.context.new_page()
            page.set_default_timeout(15000)

            # Try each slug variation
            loaded = False
            for slug in slugs_to_try:
                urls = [
                    f"{brand_url}/products/{slug}",
                    f"{brand_url}/collections/all/products/{slug}",
                ]
                for url in urls:
                    try:
                        page.goto(url, wait_until='domcontentloaded')
                        # Check if page loaded (not 404)
                        if '404' not in page.title().lower() and 'not found' not in page.title().lower():
                            loaded = True
                            break
                    except:
                        continue
                if loaded:
                    break

            if not loaded:
                page.close()
                return None

            ingredients = self.extract_ingredients_from_page(page)
            page.close()
            return ingredients

        except Exception as e:
            return None

    def get_products_without_ingredients(self, limit=None):
        """Get products that need ingredients."""
        products = []
        offset = 0
        batch_limit = 100
        collection_id = self.collection_config["id"]
        ingredients_field = self.collection_config["ingredients_field"]

        while True:
            result = self._webflow_request('GET',
                f'/collections/{collection_id}/items?limit={batch_limit}&offset={offset}')
            if not result:
                break
            items = result.get('items', [])
            if not items:
                break

            for item in items:
                fd = item.get('fieldData', {})
                ing = fd.get(ingredients_field, '') or ''
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
        collection_id = self.collection_config["id"]
        ingredients_field = self.collection_config["ingredients_field"]
        update_data = {
            'fieldData': {
                ingredients_field: ingredients_html
            }
        }
        result = self._webflow_request('PATCH',
            f'/collections/{collection_id}/items/{item_id}',
            update_data)
        return result is not None

    def run(self, limit=None):
        """Run the ingredient scraping process."""
        print("Starting headless browser...")
        self.start_browser()

        print("Fetching products without ingredients...")
        products = self.get_products_without_ingredients(limit=limit)
        print(f"Found {len(products)} products to process\n")

        if not products:
            print("No products to process")
            self.stop_browser()
            return

        stats = {
            'scraped': 0,
            'updated': 0,
            'no_brand_url': 0,
            'not_found': 0,
            'errors': 0,
        }

        try:
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
                    if stats['no_brand_url'] <= 10:
                        print(f"  [{i}/{len(products)}] {name[:40]}: No brand URL for '{brand}'")
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
                    if stats['not_found'] <= 20:
                        print(f"  [{i}/{len(products)}] {name[:40]}: No ingredients found")

                if i % 25 == 0:
                    print(f"\n  --- Progress: {i}/{len(products)} | Updated: {stats['updated']} ---\n")

        finally:
            self.stop_browser()

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

    parser = argparse.ArgumentParser(description='Scrape missing ingredients with headless browser')
    parser.add_argument('--collection', choices=['makeups', 'skincares'], default='makeups',
                        help='Which collection to process')
    parser.add_argument('--limit', type=int, help='Limit number of products')
    parser.add_argument('--all', action='store_true', help='Process all products')

    args = parser.parse_args()

    limit = None
    if args.limit:
        limit = args.limit
    elif not args.all:
        limit = 30  # Default smaller for headless

    print(f"Processing {args.collection} collection")
    scraper = HeadlessIngredientScraper(collection_name=args.collection)
    scraper.run(limit=limit)
