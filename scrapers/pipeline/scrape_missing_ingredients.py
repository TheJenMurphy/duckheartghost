#!/usr/bin/env python3
"""
Scrape ingredients for products that are missing them.
Only targets real products, skips accessories/sets.

Usage:
    python scrape_missing_ingredients.py --limit 50
    python scrape_missing_ingredients.py --all
"""

import os
import re
import sys
import json
import time
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

# Load .env
try:
    from dotenv import load_dotenv
    # Try pipeline/.env first, then parent
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
    "Jones Road Beauty": "https://jonesroadbeauty.com",
    "Jones Road": "https://jonesroadbeauty.com",
    "W3ll People": "https://w3llpeople.com",
    "W3LL PEOPLE": "https://w3llpeople.com",
    "Kjaer Weis": "https://kjaerweis.com",
    "LYS Beauty": "https://lysbeauty.com",
    "LYS": "https://lysbeauty.com",
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
    "Lys": "https://lysbeauty.com",
    "Tower 28": "https://tower28beauty.com",
    "Grown Alchemist": "https://grownalchemist.com",
}

# Keywords that indicate non-ingredient items
NON_INGREDIENT_KEYWORDS = [
    'brush', 'sponge', 'bag', 'pouch', 'keychain', 'mirror', 'case', 'holder',
    'tool', 'applicator', 'kit bag', 'travel bag', 'makeup bag', 'book', 'gift card',
    'trucker', 'hat', 'cap', 'tote', 'bundle', 'set', 'duo', 'trio', 'collection',
    'sampler', 'discovery', 'mini set', 'refill', 'sock', 'headband', 'scrunchie',
    'towel', 'cloth', 'wipe', 'zine', 'print', 'consultation', 'gift:', 'free gift',
    'sharpener', 'test -', 'parent item', 'all products', 'lash cluster'
]


class MissingIngredientsScraper:
    """Scrape ingredients for products missing them."""

    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.webflow_session = requests.Session()
        self.webflow_session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        })
        self._last_webflow_request = 0
        self._brand_cache = {}  # brand_id -> brand_name
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
        """Check if product is likely an accessory (no ingredients)."""
        name_lower = name.lower()
        return any(kw in name_lower for kw in NON_INGREDIENT_KEYWORDS)

    def get_brand_url(self, brand_name):
        """Get brand website URL."""
        if not brand_name:
            return None
        # Try exact match first
        if brand_name in BRAND_URLS:
            return BRAND_URLS[brand_name]
        # Try case-insensitive
        for key, url in BRAND_URLS.items():
            if key.lower() == brand_name.lower():
                return url
        return None

    def extract_ingredients(self, html, url):
        """Extract ingredients from product page HTML."""
        soup = BeautifulSoup(html, 'html.parser')

        # Method 1: Try Shopify JSON
        try:
            json_url = url.rstrip('/') + '.json'
            resp = requests.get(json_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                product = data.get('product', {})

                # Check metafields
                metafields = product.get('metafields', [])
                for mf in metafields:
                    if 'ingredient' in str(mf.get('key', '')).lower():
                        val = mf.get('value', '')
                        if val and len(val) > 20:
                            return val

                # Check body_html
                body = product.get('body_html', '')
                if body:
                    body_soup = BeautifulSoup(body, 'html.parser')
                    text = body_soup.get_text()
                    # Look for ingredients section
                    match = re.search(r'ingredients?[:\s]*(.{50,}?)(?=\n\n|\Z)', text, re.I | re.S)
                    if match:
                        ing_text = match.group(1).strip()
                        if len(ing_text) > 30:
                            return ing_text
        except:
            pass

        # Method 2: Look for ingredients accordion/tab
        for accordion in soup.find_all(['div', 'details', 'button'],
            class_=lambda x: x and any(k in str(x).lower() for k in ['accordion', 'tab', 'toggle', 'collapse'])):
            text = accordion.get_text().lower()
            if 'ingredient' in text:
                # Get the content
                parent = accordion.find_parent(['div', 'section'])
                if parent:
                    content = parent.get_text(separator=' ', strip=True)
                    # Extract just the ingredients part
                    match = re.search(r'ingredients?[:\s]*(.{30,})', content, re.I)
                    if match:
                        return match.group(1).strip()[:2000]

        # Method 3: Look for labeled sections
        for elem in soup.find_all(['div', 'section', 'p', 'span']):
            text = elem.get_text()
            if re.search(r'\bingredients?\s*[:\-]', text, re.I):
                full_text = elem.get_text(separator=' ', strip=True)
                # Extract ingredients
                match = re.search(r'ingredients?[:\s\-]*(.{30,})', full_text, re.I)
                if match:
                    ing = match.group(1).strip()
                    # Clean up
                    ing = re.sub(r'\s+', ' ', ing)
                    if len(ing) > 30:
                        return ing[:2000]

        # Method 4: Look for common ingredient patterns
        full_text = soup.get_text()
        patterns = [
            r'(?:full\s+)?ingredients?[:\s]*([A-Z][a-zA-Z\s,\(\)\-\d\.]+(?:,\s*[A-Za-z\s\(\)\-\d\.]+){5,})',
            r'(?:contains|made with)[:\s]*([A-Z][a-zA-Z\s,\(\)\-]+(?:,\s*[A-Za-z\s\(\)\-]+){3,})',
        ]
        for pattern in patterns:
            match = re.search(pattern, full_text)
            if match:
                ing = match.group(1).strip()
                if len(ing) > 50:
                    return ing[:2000]

        return None

    def scrape_product_ingredients(self, product_name, product_slug, brand_name):
        """Scrape ingredients for a single product."""
        brand_url = self.get_brand_url(brand_name)
        if not brand_url:
            return None

        # Construct product URL
        product_url = f"{brand_url}/products/{product_slug}"

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            resp = requests.get(product_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                # Try alternate URL patterns
                alt_urls = [
                    f"{brand_url}/collections/all/products/{product_slug}",
                    f"{brand_url}/product/{product_slug}",
                ]
                for alt_url in alt_urls:
                    resp = requests.get(alt_url, headers=headers, timeout=15)
                    if resp.status_code == 200:
                        product_url = alt_url
                        break
                else:
                    return None

            ingredients = self.extract_ingredients(resp.text, product_url)
            return ingredients

        except Exception as e:
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

                # Skip if has ingredients
                if ing.strip() and len(ing.strip()) > 20:
                    continue

                # Skip accessories
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
                if i <= 20:
                    print(f"  [{i}/{len(products)}] {name[:40]}: No brand URL for '{brand}'")
                continue

            time.sleep(0.5)  # Be nice to servers
            ingredients = self.scrape_product_ingredients(name, slug, brand)

            if ingredients:
                stats['scraped'] += 1
                # Format as HTML
                ing_html = f"<p>{ingredients}</p>"

                if self.update_product(item_id, ing_html):
                    stats['updated'] += 1
                    print(f"  [{i}/{len(products)}] {name[:40]}: Updated ({len(ingredients)} chars)")
                else:
                    stats['errors'] += 1
                    print(f"  [{i}/{len(products)}] {name[:40]}: Update failed")
            else:
                stats['not_found'] += 1
                if stats['not_found'] <= 30:
                    print(f"  [{i}/{len(products)}] {name[:40]}: No ingredients found")

            if i % 50 == 0:
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

    parser = argparse.ArgumentParser(description='Scrape missing ingredients')
    parser.add_argument('--limit', type=int, help='Limit number of products')
    parser.add_argument('--all', action='store_true', help='Process all products')

    args = parser.parse_args()

    limit = None
    if args.limit:
        limit = args.limit
    elif not args.all:
        limit = 50  # Default

    scraper = MissingIngredientsScraper()
    scraper.run(limit=limit)
