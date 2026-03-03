#!/usr/bin/env python3
"""
Scrape all 9S attributes from brand product pages.

Fills in missing: safety, support, suitability, substance, sustainability, structure

Usage:
    python scrape_all_attributes.py --dry-run --limit 10
    python scrape_all_attributes.py --live --all
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

# Attribute patterns organized by category
ATTRIBUTE_PATTERNS = {
    'safety-attributes': {
        'clean': [r'\bclean\s+(?:beauty|formula|ingredient)', r'\bclean-beauty\b'],
        'non-toxic': [r'non[\s-]*toxic', r'toxin[\s-]*free'],
        'ewg-verified': [r'ewg[\s-]*verified', r'ewg\s+skin\s+deep'],
        'fragrance-free': [r'fragrance[\s-]*free', r'unscented', r'no\s+(?:added\s+)?fragrance'],
        'hypoallergenic': [r'hypo[\s-]*allergenic', r'allergy[\s-]*tested'],
        'pregnancy-safe': [r'pregnancy[\s-]*safe', r'safe\s+(?:for|during)\s+pregnancy', r'bump[\s-]*safe'],
        'dermatologist-tested': [r'dermatologist[\s-]*tested', r'derm[\s-]*tested', r'dermatologist[\s-]*approved'],
        'paraben-free': [r'paraben[\s-]*free', r'no\s+parabens'],
        'sulfate-free': [r'sulfate[\s-]*free', r'no\s+sulfates', r'sls[\s-]*free'],
        'phthalate-free': [r'phthalate[\s-]*free', r'no\s+phthalates'],
        'silicone-free': [r'silicone[\s-]*free', r'no\s+silicones'],
        'gluten-free': [r'gluten[\s-]*free'],
        'alcohol-free': [r'alcohol[\s-]*free', r'no\s+alcohol'],
    },
    'support-attributes': {
        'hydrating': [r'\bhydrat(?:ing|ion|e)', r'deeply\s+moisturiz'],
        'moisturizing': [r'\bmoisturiz(?:ing|er|e)', r'locks?\s+in\s+moisture'],
        'soothing': [r'\bsooth(?:ing|e|es)', r'calm(?:ing|s)'],
        'anti-aging': [r'anti[\s-]*ag(?:ing|e)', r'reduces?\s+(?:fine\s+)?(?:lines|wrinkles)', r'youthful'],
        'brightening': [r'brighten(?:ing|s)?', r'radiance', r'luminous', r'glow(?:ing)?'],
        'firming': [r'firm(?:ing|s)?', r'tighten(?:ing|s)?', r'lift(?:ing|s)?'],
        'smoothing': [r'smooth(?:ing|s|er)?', r'blur(?:ring|s)?', r'refin(?:ing|e|es)'],
        'long-wearing': [r'long[\s-]*wear(?:ing)?', r'all[\s-]*day', r'24[\s-]*hour', r'lasts?\s+all\s+day'],
        'transfer-proof': [r'transfer[\s-]*(?:proof|resistant|free)', r'no[\s-]*transfer'],
        'water-resistant': [r'water[\s-]*(?:proof|resistant)', r'sweat[\s-]*(?:proof|resistant)'],
        'buildable': [r'buildable', r'build(?:s)?\s+coverage'],
        'non-greasy': [r'non[\s-]*greasy', r'oil[\s-]*free', r'lightweight'],
    },
    'suitability-attributes': {
        'all-skin-types': [r'all\s+skin\s+types', r'every\s+skin\s+type', r'universal'],
        'sensitive-skin': [r'sensitive\s+skin', r'for\s+sensitive', r'gentle\s+(?:on|for)'],
        'dry-skin': [r'dry\s+skin', r'for\s+dry', r'dehydrated\s+skin'],
        'oily-skin': [r'oily\s+skin', r'for\s+oily', r'oil[\s-]*control'],
        'combination-skin': [r'combination\s+skin', r'for\s+combination'],
        'mature-skin': [r'mature\s+skin', r'aging\s+skin', r'for\s+mature'],
        'acne-prone': [r'acne[\s-]*prone', r'blemish[\s-]*prone', r'breakout'],
        'rosacea-safe': [r'rosacea[\s-]*(?:safe|friendly)', r'for\s+rosacea'],
        'eczema-safe': [r'eczema[\s-]*(?:safe|friendly)', r'for\s+eczema'],
        'inclusive-shades': [r'inclusive\s+shade', r'\d+\+?\s+shades', r'wide\s+(?:range|variety)\s+of\s+shades'],
    },
    'substance-attributes': {
        'retinol': [r'\bretinol\b', r'\bretinoid\b', r'vitamin\s+a\b'],
        'vitamin-c': [r'vitamin\s+c\b', r'\bascorbic\s+acid', r'l-ascorbic'],
        'niacinamide': [r'\bniacinamide\b', r'vitamin\s+b3'],
        'hyaluronic-acid': [r'hyaluronic\s+acid', r'\bha\b(?!\s*ha)', r'sodium\s+hyaluronate'],
        'peptides': [r'\bpeptide', r'collagen[\s-]*boosting'],
        'aha-bha': [r'\baha\b', r'\bbha\b', r'glycolic\s+acid', r'salicylic\s+acid', r'lactic\s+acid'],
        'spf': [r'\bspf\s*\d+', r'sun\s*(?:screen|block|protection)', r'broad\s+spectrum'],
        'ceramides': [r'\bceramide'],
        'squalane': [r'\bsqualane\b', r'\bsqualene\b'],
        'bakuchiol': [r'\bbakuchiol\b'],
        'centella': [r'\bcentella\b', r'\bcica\b', r'tiger\s+grass'],
        'aloe': [r'\baloe\s+vera\b', r'\baloe\b'],
        'caffeine': [r'\bcaffeine\b'],
    },
    'sustainability-attributes': {
        'vegan': [r'\bvegan\b', r'100%\s+vegan', r'plant[\s-]*based'],
        'cruelty-free': [r'cruelty[\s-]*free', r'not\s+tested\s+on\s+animals', r'no\s+animal\s+testing'],
        'leaping-bunny': [r'leaping\s+bunny', r'peta[\s-]*(?:certified|approved)'],
        'certified-organic': [r'certified\s+organic', r'usda\s+organic', r'ecocert'],
        'sustainably-sourced': [r'sustainabl[ye][\s-]*(?:sourced|made|produced)', r'responsibly\s+sourced'],
        'recyclable-packaging': [r'recyclable\s+(?:packaging|materials?)', r'recycle(?:d|able)'],
        'refillable': [r'\brefill(?:able|s)?\b', r'refill\s+(?:system|pod|cartridge)'],
        'reef-safe': [r'reef[\s-]*safe', r'ocean[\s-]*(?:safe|friendly)'],
        'biodegradable': [r'bio[\s-]*degradable'],
        'carbon-neutral': [r'carbon[\s-]*neutral', r'climate[\s-]*(?:neutral|positive)'],
    },
    'structure-attributes-2': {
        'pump': [r'\bpump\s+(?:bottle|dispenser|top)', r'airless\s+pump'],
        'dropper': [r'\bdropper\b', r'pipette'],
        'tube': [r'\btube\b', r'squeeze\s+tube'],
        'jar': [r'\bjar\b', r'pot\s+(?:container|packaging)'],
        'spray': [r'\bspray\b', r'mist(?:er|ing)?', r'atomizer'],
        'stick': [r'\bstick\s+(?:form|format)', r'twist[\s-]*up\s+stick'],
        'compact': [r'\bcompact\b', r'pressed\s+(?:powder|compact)'],
        'palette': [r'\bpalette\b'],
        'pencil': [r'\bpencil\b', r'crayon'],
        'travel-size': [r'travel[\s-]*size', r'mini\b', r'deluxe\s+(?:mini|sample)', r'to[\s-]*go\s+size'],
        'refillable-packaging': [r'refillable\s+(?:packaging|case|compact)'],
    },
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


def detect_attributes(html: str, category: str) -> Set[str]:
    """Detect attributes for a specific category from page content."""
    if not html or category not in ATTRIBUTE_PATTERNS:
        return set()

    # Clean HTML
    clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.I)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.I)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = re.sub(r'&[a-z]+;', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).lower()

    found = set()
    patterns = ATTRIBUTE_PATTERNS[category]

    for attr, attr_patterns in patterns.items():
        for pattern in attr_patterns:
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


def merge_attributes(existing: str, new: Set[str]) -> str:
    """Merge new attributes with existing ones."""
    if not existing:
        return ', '.join(sorted(new))

    existing_set = set(a.strip() for a in existing.split(',') if a.strip())
    merged = existing_set | new
    return ', '.join(sorted(merged))


def main():
    print("=" * 70)
    print("SCRAPE ALL 9S ATTRIBUTES FROM BRAND WEBSITES")
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

    # Categories to scrape (field name -> display name)
    categories = [
        ('safety-attributes', 'Safety'),
        ('support-attributes', 'Support'),
        ('suitability-attributes', 'Suitability'),
        ('substance-attributes', 'Substance'),
        ('sustainability-attributes', 'Sustainability'),
        ('structure-attributes-2', 'Structure'),
    ]

    # Find products with product-url that could use more attributes
    to_process = []
    for item in products:
        fd = item.get('fieldData', {})
        product_url = (fd.get('product-url', '') or '').strip()

        if not product_url:
            continue

        # Check if any category could use more data
        needs_update = False
        for field, _ in categories:
            current = (fd.get(field, '') or '').strip()
            # Process if field is empty or has few attributes
            if not current or current.count(',') < 2:
                needs_update = True
                break

        if needs_update:
            to_process.append(item)

    print(f"Products to check for attributes: {len(to_process)}")

    if limit:
        to_process = to_process[:limit]
        print(f"Processing: {len(to_process)}")
    print()

    if not to_process:
        print("No products to process!")
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

        # Detect attributes for each category
        updates = {}
        found_any = False

        for field, display in categories:
            existing = (fd.get(field, '') or '').strip()
            new_attrs = detect_attributes(html, field)

            if new_attrs:
                merged = merge_attributes(existing, new_attrs)
                if merged != existing:
                    updates[field] = merged
                    found_any = True
                    if i <= 20:
                        print(f"  {display}: +{', '.join(new_attrs)}")

        if not found_any:
            if i <= 20:
                print(f"  (no new attributes)")
            skipped += 1
            time.sleep(0.2)
            continue

        if not dry_run:
            if updater.update_product(item_id, updates):
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
    print(f"No new attributes: {skipped}")
    print(f"Errors: {errors}")

    if dry_run:
        print()
        print("[DRY RUN] No changes made. Run with --live to apply.")


if __name__ == '__main__':
    main()
