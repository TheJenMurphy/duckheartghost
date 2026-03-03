#!/usr/bin/env python3
"""
Scrape product metadata (product type, skin type, etc.) for products.

Usage:
    python scrape_product_metadata.py --collection makeups --dry-run --limit 10
    python scrape_product_metadata.py --collection makeups --live
    python scrape_product_metadata.py --collection skincares --live
"""

import os
import sys
import time
import re
import json
from pathlib import Path
from typing import Dict, List, Optional
import functools

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

import requests
print = functools.partial(print, flush=True)

WEBFLOW_API_BASE = "https://api.webflow.com/v2"

COLLECTIONS = {
    'makeups': '697d3803e654519eef084068',
    'skincares': '697d723c3df8451b1f1cce1a',
}

# Product type mappings - maps to Webflow Option IDs
PRODUCT_TYPE_MAP = {
    # Makeup
    'Concealer': {'id': '64b9b3f2db05915b38278eaef384e1fd', 'keywords': ['concealer']},
    'Foundation': {'id': 'bfe3813f1b33de19ec70024ef1ae7a1e', 'keywords': ['foundation']},
    'Tinted Moisturizer': {'id': '64ffaffdbca852be7190f8e604957a47', 'keywords': ['tinted moisturizer', 'bb cream', 'cc cream']},
    'Powder': {'id': 'b52460b5a4dbbdd8a52788a9556d69b9', 'keywords': ['powder', 'setting powder']},
    'Blush': {'id': 'f21812fb140303ee69271e4535ec3fa5', 'keywords': ['blush', 'cheek tint']},
    'Bronzer': {'id': 'a2c993861f9968ef0e3a813df0dc61da', 'keywords': ['bronzer']},
    'Contour': {'id': 'd2c2b261259c2df0a0ded4d9ee02f235', 'keywords': ['contour']},
    'Highlighter': {'id': '33c408985066e020f2f4bbea16e6f077', 'keywords': ['highlighter', 'illuminat']},
    'Primer': {'id': '9c8e710ed5ef72465476c01f446302be', 'keywords': ['primer']},
    'Mascara': {'id': 'da0ba04a6887f4ad222055fa61dcedde', 'keywords': ['mascara']},
    'Eyeliner': {'id': '73181470047c4389620df4e4f2a9f89f', 'keywords': ['eyeliner', 'eye liner', 'kohl']},
    'Brow': {'id': '3561b1f12fb003d341db7534ddb836f3', 'keywords': ['brow', 'eyebrow']},
    'Eyeshadow': {'id': 'd234cc1219ed75cf7cbeed033af007c7', 'keywords': ['eyeshadow', 'eye shadow']},
    'Eye Palette': {'id': 'cde75d06917b06d2f95781374cc8801e', 'keywords': ['eye palette', 'shadow palette']},
    'Lip Liner': {'id': '4639e5b0117926981cf139764efef608', 'keywords': ['lip liner']},
    'Lip Gloss': {'id': '77e0ebffc8a10c63bb1d3931066777fa', 'keywords': ['lip gloss', 'gloss']},
    'Lipstick': {'id': '4e622c01c507413488657d590cdcd66e', 'keywords': ['lipstick']},
    'Lip Oil': {'id': '09505b28a5bf3f53ccef5cbfdf6e7f7a', 'keywords': ['lip oil']},
    'Tinted Lip Balm': {'id': '9222e7e4b12818cbc9f380b23d63b7af', 'keywords': ['tinted lip balm', 'lip tint']},
    'Multi-Use': {'id': '0a24d389efc0ca1570e98a0602a7aa24', 'keywords': ['multi-use', 'lip2cheek', 'multipurpose']},
    # Skincare
    'Cleanser': {'id': '3793a918de86ba3a0a5817ef179d732a', 'keywords': ['cleanser', 'cleansing']},
    'Face Wash': {'id': 'aefcf35af978ac0665a85ff742b2c064', 'keywords': ['face wash', 'facial wash']},
    'Toner': {'id': 'e39dbbf592c86be7f26fdee82cdd9e98', 'keywords': ['toner', 'tonic']},
    'Exfoliant': {'id': 'b1054ccec3815705b4f072c987e09a79', 'keywords': ['exfoliant', 'exfoliator', 'scrub']},
    'Serum': {'id': '9c46e652ca28f95a4b67a124e187ab84', 'keywords': ['serum', 'concentrate', 'ampoule']},
    'Mask': {'id': '5c7fd7391e385fa9faced84159d17bba', 'keywords': ['mask', 'masque']},
    'Peel': {'id': 'e3bb3449cfa80c308c72553b4281906f', 'keywords': ['peel']},
    'Spot Treatment': {'id': '542e9f364c10372f3e89d9299bc85973', 'keywords': ['spot treatment', 'blemish']},
    'Face Cream': {'id': '1d826d81ba562809983e6594bd00c9e8', 'keywords': ['face cream', 'facial cream']},
    'Moisturizer': {'id': '9b52773294d4f2f740bea196c3e46656', 'keywords': ['moisturizer', 'moisturiser', 'hydrat']},
    'Oil': {'id': 'c6285736f6101f887075b7d31e425387', 'keywords': ['face oil', 'facial oil', 'oil serum']},
    'Mist': {'id': 'bc288c1e518e974aef486ad03301a50b', 'keywords': ['mist', 'spray']},
    'Essence': {'id': '672a5159801637738fd7ec603502d1db', 'keywords': ['essence']},
    'Eye Cream': {'id': '5436ec7afbb552f06b4263a741952911', 'keywords': ['eye cream', 'eye gel']},
    'Eye Treatment': {'id': '3b009446301eed45869d18067eae205d', 'keywords': ['eye treatment', 'eye serum', 'under eye']},
    'Sunscreen': {'id': '8a6cece6a7a536af6aeacd5d1a468ae8', 'keywords': ['sunscreen', 'spf', 'sun protection']},
    'Retinol Treatment': {'id': '6b5972e909c737b52e8c211ad36ebb58', 'keywords': ['retinol', 'retinal', 'retinoid']},
    'Lip Treatment': {'id': '0a88df274eb16fab79413e7e06fccd2f', 'keywords': ['lip treatment', 'lip mask', 'lip balm']},
    'Lip Care': {'id': '8f7fe59b59012d0d1c2fcfe6454bc1b4', 'keywords': ['lip care']},
    # Body
    'Body Wash': {'id': '96624cc87335cdb63ff121e0e62d428f', 'keywords': ['body wash', 'shower gel']},
    'Body Cream': {'id': '7952f77fba97cf120eaeecaa8acdec57', 'keywords': ['body cream', 'body butter']},
    'Body Lotion': {'id': '01b8cef54c2d6aa26609a99fb3e6b18b', 'keywords': ['body lotion']},
    'Body Oil': {'id': '8435e2be7024c05d59754c474bd8a633', 'keywords': ['body oil']},
    'Body Serum': {'id': '4384f0a541c5c3f22fe694f4b980e29d', 'keywords': ['body serum']},
    'Hand Cream': {'id': '4d8e84a761a3a84d4e0e5e0667966f88', 'keywords': ['hand cream', 'hand lotion']},
    'Deodorant': {'id': '5c3ab49f54e2fbe0cc9fd31beefea5be', 'keywords': ['deodorant']},
    'Fragrance': {'id': '253b8a238b8eb245d1d54c613cdde45e', 'keywords': ['fragrance', 'perfume', 'eau de']},
    'Makeup Remover': {'id': 'ed8de6a934aae28f1a53b51584b52114', 'keywords': ['makeup remover', 'cleansing balm']},
    'Balm': {'id': '6c54305ca1066c4b3f2e4bdaec0ab49f', 'keywords': ['balm']},
}

def extract_product_type(html: str, name: str) -> Optional[Dict]:
    """Extract product type from HTML and product name. Returns {id, name}."""
    # Prioritize matching against product name first (more reliable)
    name_lower = name.lower()

    for ptype_name, config in PRODUCT_TYPE_MAP.items():
        for kw in config['keywords']:
            if kw in name_lower:
                return {'id': config['id'], 'name': ptype_name}

    # Fall back to HTML content - but be more careful
    # Look for product type in structured data or specific sections
    html_lower = html.lower()

    # Try to find product type in JSON-LD or meta tags
    import re
    type_patterns = [
        r'"product_type"\s*:\s*"([^"]+)"',
        r'"category"\s*:\s*"([^"]+)"',
        r'<meta[^>]*property="product:category"[^>]*content="([^"]+)"',
    ]

    for pattern in type_patterns:
        match = re.search(pattern, html_lower)
        if match:
            found_type = match.group(1).lower()
            for ptype_name, config in PRODUCT_TYPE_MAP.items():
                for kw in config['keywords']:
                    if kw in found_type:
                        return {'id': config['id'], 'name': ptype_name}

    return None




def fetch_product_data(url: str) -> Optional[str]:
    """Fetch product HTML."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 5000:
            return resp.text
    except:
        pass

    return None


class WebflowClient:
    def __init__(self, collection_id: str):
        self.collection_id = collection_id
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
        })
        self._last_request = 0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
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

    def get_all_items(self) -> List[Dict]:
        items = []
        offset = 0
        while True:
            result = self._request('GET', f'/collections/{self.collection_id}/items?limit=100&offset={offset}')
            if not result or not result.get('items'):
                break
            items.extend(result['items'])
            if len(result['items']) < 100:
                break
            offset += 100
        return items

    def update_item(self, item_id: str, field_data: Dict) -> bool:
        data = {
            'isArchived': False,
            'isDraft': False,
            'fieldData': field_data
        }
        result = self._request('PATCH', f'/collections/{self.collection_id}/items/{item_id}', json_data=data)
        return result is not None


def main():
    print("=" * 70)
    print("SCRAPE PRODUCT METADATA")
    print("=" * 70)

    args = sys.argv[1:]
    dry_run = '--live' not in args

    collection = 'makeups'
    for i, arg in enumerate(args):
        if arg == '--collection' and i + 1 < len(args):
            collection = args[i + 1]

    if collection not in COLLECTIONS:
        print(f"Unknown collection: {collection}")
        return

    limit = None
    offset = 0
    for i, arg in enumerate(args):
        if arg == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1])
        if arg == '--offset' and i + 1 < len(args):
            offset = int(args[i + 1])

    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Collection: {collection}")

    client = WebflowClient(COLLECTIONS[collection])

    print("\nLoading collection...")
    items = client.get_all_items()
    print(f"  Found {len(items)} products")

    # Find products missing product-type
    to_scrape = []
    for item in items:
        fd = item.get('fieldData', {})
        name = fd.get('name', '')
        url = fd.get('external-link', '') or ''
        product_type = fd.get('product-type', '')

        # Skip if already has product type
        if product_type:
            continue

        if not url:
            continue

        to_scrape.append({
            'id': item['id'],
            'name': name,
            'url': url,
        })

    print(f"  Products missing product-type: {len(to_scrape)}")

    if offset:
        to_scrape = to_scrape[offset:]
        print(f"  Starting from offset: {offset}")

    if limit:
        to_scrape = to_scrape[:limit]
        print(f"  Limited to: {limit}")

    # Scrape each product
    updated = 0
    failed = 0

    for i, product in enumerate(to_scrape):
        print(f"\n[{i+1}/{len(to_scrape)}] {product['name'][:50]}")

        # Fetch HTML
        html = fetch_product_data(product['url'])
        if not html:
            print("  ✗ Failed to fetch")
            failed += 1
            continue

        # Extract product type
        ptype = extract_product_type(html, product['name'])
        if not ptype:
            print("  No product type found")
            continue

        print(f"  Product type: {ptype['name']}")

        updates = {
            'product-type': ptype['id'],
            'product-type-name': ptype['name'],
        }

        # Update Webflow
        if not dry_run:
            if client.update_item(product['id'], updates):
                print("  ✓ Updated")
                updated += 1
            else:
                print("  ✗ Update failed")
                failed += 1
        else:
            updated += 1

        time.sleep(0.3)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Processed: {len(to_scrape)}")
    print(f"  Updated: {updated}")
    print(f"  Failed: {failed}")

    if dry_run:
        print("\n[DRY RUN] No changes made. Run with --live to apply.")


if __name__ == '__main__':
    main()
