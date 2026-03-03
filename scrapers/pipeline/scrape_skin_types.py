#!/usr/bin/env python3
"""
Scrape skin type and SPF information from product pages.

Extracts skin type from:
- Product descriptions
- "Good for" / "Best for" sections
- Structured product data

Extracts SPF value if explicitly listed.

Usage:
    python scrape_skin_types.py --collection makeups --dry-run
    python scrape_skin_types.py --collection skincares --live
"""

import os
import sys
import time
import re
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

import requests
from bs4 import BeautifulSoup

WEBFLOW_API_BASE = "https://api.webflow.com/v2"

COLLECTIONS = {
    "makeups": "697d3803e654519eef084068",
    "skincares": "697d723c3df8451b1f1cce1a",
    "tools": "697d7d4a824e85c10e862dd1",
}

# Valid skin type options in Webflow
SKIN_TYPE_OPTIONS = ['Mature', 'Dry', 'Dehydrated', 'Sensitive', 'Combination', 'Oily', 'Acne-Prone']

# Patterns to detect skin types in text
SKIN_TYPE_PATTERNS = {
    'Mature': [r'\bmature\b', r'\baging\b', r'\banti-aging\b', r'\bfine lines\b', r'\bwrinkles\b'],
    'Dry': [r'\bdry\b(?!\s*skin\s*types)', r'\bdry skin\b', r'\bvery dry\b'],
    'Dehydrated': [r'\bdehydrated\b', r'\blacks moisture\b', r'\bthirsty skin\b'],
    'Sensitive': [r'\bsensitive\b', r'\breactive\b', r'\beasily irritated\b', r'\bredness\b'],
    'Combination': [r'\bcombination\b', r'\bmixed\b', r'\bt-zone\b'],
    'Oily': [r'\boily\b', r'\bexcess oil\b', r'\bshine control\b', r'\bmattifying\b'],
    'Acne-Prone': [r'\bacne\b', r'\bblemish\b', r'\bbreakout\b', r'\bprone to breakouts\b', r'\bpimple\b'],
}

# "All skin types" patterns - means we should set all types
ALL_TYPES_PATTERNS = [
    r'\ball skin types\b',
    r'\beveryone\b',
    r'\buniversal\b',
    r'\bany skin type\b',
]

# SPF extraction patterns - captures the numeric value
SPF_PATTERNS = [
    r'\bSPF\s*(\d+)\b',
    r'\bspf\s*(\d+)\b',
    r'\bSun\s*Protection\s*Factor\s*(\d+)\b',
    r'\bBroad\s*Spectrum\s*SPF\s*(\d+)\b',
    r'\bSPF(\d+)\b',  # No space between SPF and number
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}


def extract_skin_types_from_text(text: str) -> List[str]:
    """Extract skin types mentioned in text."""
    if not text:
        return []

    text_lower = text.lower()
    found_types = set()

    # Check for "all skin types" first
    for pattern in ALL_TYPES_PATTERNS:
        if re.search(pattern, text_lower):
            # Return all types except maybe Acne-Prone (specific concern)
            return ['Mature', 'Dry', 'Dehydrated', 'Sensitive', 'Combination', 'Oily']

    # Check for specific skin types
    for skin_type, patterns in SKIN_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                found_types.add(skin_type)
                break

    return list(found_types)


def extract_spf_from_text(text: str) -> Optional[int]:
    """Extract SPF value from text. Returns None if not found."""
    if not text:
        return None

    for pattern in SPF_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                spf_value = int(match.group(1))
                # Sanity check - SPF values are typically 15-100
                if 10 <= spf_value <= 120:
                    return spf_value
            except (ValueError, IndexError):
                continue

    return None


def get_data_from_shopify(url: str) -> Dict:
    """Extract skin type and SPF from Shopify product JSON."""
    result = {'skin_types': [], 'spf': None}

    try:
        json_url = url.rstrip('/') + '.json'
        resp = requests.get(json_url, headers=HEADERS, timeout=15)

        if resp.ok:
            data = resp.json()
            product = data.get('product', {})

            # Get all text to check
            body = product.get('body_html', '') or ''
            title = product.get('title', '') or ''
            tags = ' '.join(product.get('tags', []))
            all_text = f"{title} {body} {tags}"

            # Extract SPF from any text
            result['spf'] = extract_spf_from_text(all_text)

            # Extract skin types
            types = extract_skin_types_from_text(body)
            if not types:
                types = extract_skin_types_from_text(tags)
            result['skin_types'] = types

    except Exception:
        pass

    return result


def get_data_from_html(url: str) -> Dict:
    """Extract skin type and SPF from HTML page."""
    result = {'skin_types': [], 'spf': None}

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if not resp.ok:
            return result

        soup = BeautifulSoup(resp.text, 'html.parser')
        page_text = soup.get_text()

        # Extract SPF from page
        result['spf'] = extract_spf_from_text(page_text)

        # Look for skin type in specific sections
        skin_sections = soup.find_all(string=re.compile(r'skin\s*type|good\s*for|best\s*for|suitable\s*for', re.I))

        for section in skin_sections:
            parent = section.find_parent(['div', 'section', 'p', 'li', 'span'])
            if parent:
                text = parent.get_text()
                types = extract_skin_types_from_text(text)
                if types:
                    result['skin_types'] = types
                    return result

        # Check product description areas
        desc_selectors = [
            '.product-description',
            '.product-details',
            '.pdp-description',
            '[data-product-description]',
            '.product__description',
            '#product-description',
        ]

        for selector in desc_selectors:
            desc = soup.select_one(selector)
            if desc:
                types = extract_skin_types_from_text(desc.get_text())
                if types:
                    result['skin_types'] = types
                    return result

        # Fallback: check entire page text (less accurate)
        result['skin_types'] = extract_skin_types_from_text(page_text)

    except Exception:
        pass

    return result


def get_product_data_from_url(url: str) -> Dict:
    """Get skin type and SPF from product URL."""
    if not url:
        return {'skin_type': None, 'spf': None}

    result = {'skin_type': None, 'spf': None}

    # Try Shopify first
    if '/products/' in url:
        data = get_data_from_shopify(url)
        if data['skin_types']:
            result['skin_type'] = data['skin_types'][0]  # Option field takes single value
        if data['spf']:
            result['spf'] = data['spf']
        if result['skin_type'] or result['spf']:
            return result

    # Fallback to HTML parsing
    data = get_data_from_html(url)
    if data['skin_types'] and not result['skin_type']:
        result['skin_type'] = data['skin_types'][0]
    if data['spf'] and not result['spf']:
        result['spf'] = data['spf']

    return result


class WebflowClient:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
        })

    def get_items(self, collection_id: str) -> List[Dict]:
        items = []
        offset = 0

        while True:
            url = f'{WEBFLOW_API_BASE}/collections/{collection_id}/items?limit=100&offset={offset}'
            resp = self.session.get(url)

            if resp.status_code == 429:
                time.sleep(int(resp.headers.get('Retry-After', 60)))
                continue

            if not resp.ok:
                break

            data = resp.json()
            batch = data.get('items', [])
            items.extend(batch)

            if len(batch) < 100:
                break
            offset += 100
            time.sleep(0.5)

        return items

    def update_item(self, collection_id: str, item_id: str, item_name: str, field_data: Dict) -> bool:
        url = f'{WEBFLOW_API_BASE}/collections/{collection_id}/items/{item_id}'

        # Include name field (required for Webflow PATCH)
        field_data['name'] = item_name

        payload = {
            'isArchived': False,
            'isDraft': False,
            'fieldData': field_data
        }

        resp = self.session.patch(url, json=payload, headers={'Content-Type': 'application/json'})

        if resp.status_code == 429:
            time.sleep(int(resp.headers.get('Retry-After', 60)))
            return self.update_item(collection_id, item_id, item_name, field_data)

        if not resp.ok:
            print(f" Error {resp.status_code}: {resp.text[:200]}")

        return resp.ok


def process_collection(client: WebflowClient, collection_name: str, dry_run: bool = True, limit: int = 0):
    """Process a collection to fill skin types and SPF values."""
    collection_id = COLLECTIONS.get(collection_name)
    if not collection_id:
        print(f"Unknown collection: {collection_name}")
        return

    print(f"\n{'='*70}", flush=True)
    print(f"Scraping Skin Types & SPF for: {collection_name.upper()}", flush=True)
    print(f"{'='*70}", flush=True)

    items = client.get_items(collection_id)
    print(f"Loaded {len(items)} items", flush=True)

    # Find items missing skin type OR spf-value (with URLs)
    needs_update = []
    for item in items:
        fd = item.get('fieldData', {})
        skin_type = fd.get('skin-type')
        spf_value = fd.get('spf-value')
        external_link = fd.get('external-link')

        # Process if missing either field and has URL
        if external_link and (not skin_type or not spf_value):
            needs_update.append(item)

    print(f"Items needing data (with URLs): {len(needs_update)}", flush=True)

    if limit > 0:
        needs_update = needs_update[:limit]
        print(f"Processing first {limit} items", flush=True)

    updated = 0
    skin_found = 0
    spf_found = 0

    for i, item in enumerate(needs_update, 1):
        item_id = item['id']
        fd = item.get('fieldData', {})
        name = fd.get('name', 'Unknown')
        url = fd.get('external-link', '')
        existing_skin = fd.get('skin-type')
        existing_spf = fd.get('spf-value')

        print(f"[{i}/{len(needs_update)}] {name[:40]}...", end=" ")

        # Get data from product page
        data = get_product_data_from_url(url)

        # Build update fields
        update_fields = {}
        found_info = []

        # Only update skin type if not already set
        if not existing_skin and data['skin_type'] and data['skin_type'] in SKIN_TYPE_OPTIONS:
            update_fields['skin-type'] = data['skin_type']
            found_info.append(f"Skin: {data['skin_type']}")
            skin_found += 1

        # Only update SPF if not already set and found
        if not existing_spf and data['spf']:
            update_fields['spf-value'] = data['spf']
            found_info.append(f"SPF: {data['spf']}")
            spf_found += 1

        if found_info:
            print(f"Found: {', '.join(found_info)}")

            if not dry_run and update_fields:
                if client.update_item(collection_id, item_id, name, update_fields):
                    updated += 1
                time.sleep(0.5)
            else:
                updated += 1
        else:
            print("Not found")

        time.sleep(1)  # Rate limiting

    print(f"\n{'='*70}")
    print(f"Found skin types: {skin_found}")
    print(f"Found SPF values: {spf_found}")
    print(f"{'Updated' if not dry_run else 'Would update'}: {updated}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape skin types and SPF")
    parser.add_argument("--collection", default="skincares,makeups", help="Collection name(s), comma-separated or 'all'")
    parser.add_argument("--limit", type=int, default=0, help="Limit items to process per collection")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.live:
        print("Specify --dry-run or --live")
        return

    dry_run = not args.live

    print("=" * 70, flush=True)
    print("SCRAPE SKIN TYPES & SPF", flush=True)
    print("=" * 70, flush=True)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}", flush=True)

    # Parse collections
    if args.collection == 'all':
        collections = ['skincares', 'makeups']
    else:
        collections = [c.strip() for c in args.collection.split(',')]

    client = WebflowClient()

    for collection in collections:
        process_collection(client, collection, dry_run, args.limit)

    print("\nDone!")


if __name__ == "__main__":
    main()
