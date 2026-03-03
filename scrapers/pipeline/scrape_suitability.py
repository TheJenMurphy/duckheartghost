#!/usr/bin/env python3
"""
Scrape suitability data from product pages including:
- Skin types
- Product compatibility
- Routine step (prep, cleanse, treat, moisturize, protect, finish)

Updates suitability-attributes field.

Usage:
    python scrape_suitability.py --dry-run --limit 50
    python scrape_suitability.py
"""

import os
import re
import time
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

WEBFLOW_API_BASE = "https://api.webflow.com/v2"
PRODUCTS_COLLECTION_ID = "697d3803e654519eef084068"

# Skin type keywords
SKIN_TYPE_KEYWORDS = {
    'all skin': 'All Skin',
    'all skin types': 'All Skin',
    'universal': 'All Skin',
    'every skin': 'All Skin',
    'any skin': 'All Skin',
    'suitable for all': 'All Skin',
    'normal skin': 'All Skin',
    'dry skin': 'Dry',
    'dry': 'Dry',
    'parched': 'Dry',
    'oily skin': 'Oily',
    'oily': 'Oily',
    'combination skin': 'Combination',
    'combination': 'Combination',
    'sensitive skin': 'Sensitive',
    'sensitive': 'Sensitive',
    'gentle': 'Sensitive',
    'acne-prone': 'Acne-Prone',
    'acne prone': 'Acne-Prone',
    'breakout': 'Acne-Prone',
    'blemish-prone': 'Acne-Prone',
    'dehydrated': 'Dehydrated',
    'melanin-rich': 'Melanin-Rich',
    'melanin rich': 'Melanin-Rich',
    'mature skin': 'Mature',
    'aging skin': 'Mature',
}

# Routine step keywords
ROUTINE_STEPS = {
    'cleanse': 'Cleanse',
    'cleanser': 'Cleanse',
    'wash': 'Cleanse',
    'prep': 'Prep',
    'prime': 'Prep',
    'primer': 'Prep',
    'tone': 'Prep',
    'toner': 'Prep',
    'exfoliate': 'Exfoliate',
    'exfoliant': 'Exfoliate',
    'peel': 'Exfoliate',
    'scrub': 'Exfoliate',
    'treat': 'Treat',
    'serum': 'Treat',
    'treatment': 'Treat',
    'mask': 'Treat',
    'essence': 'Treat',
    'ampoule': 'Treat',
    'moisturize': 'Moisturize',
    'moisturizer': 'Moisturize',
    'cream': 'Moisturize',
    'lotion': 'Moisturize',
    'hydrate': 'Moisturize',
    'protect': 'Protect',
    'sunscreen': 'Protect',
    'spf': 'Protect',
    'sun protect': 'Protect',
    'finish': 'Finish',
    'setting': 'Finish',
    'powder': 'Finish',
    'spray': 'Finish',
}

# Compatibility keywords
COMPATIBILITY_KEYWORDS = {
    'use with': True,
    'pair with': True,
    'combine with': True,
    'layer with': True,
    'follow with': True,
    'before': True,
    'after': True,
    'works well with': True,
    'pairs well': True,
    'complement': True,
}


def get_webflow_token():
    token = os.environ.get('WEBFLOW_API_TOKEN') or os.environ.get('WEBFLOW_API_KEY', '')
    if not token:
        raise ValueError("WEBFLOW_API_TOKEN required")
    return token


def get_all_items(token, collection_id):
    items = []
    offset = 0
    while True:
        resp = requests.get(
            f'{WEBFLOW_API_BASE}/collections/{collection_id}/items?limit=100&offset={offset}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=30
        )
        if not resp.ok:
            break
        batch = resp.json().get('items', [])
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        offset += 100
        time.sleep(0.3)
    return items


def scrape_product(url, session):
    """Scrape a product page."""
    html = ''
    text = ''

    json_url = url.rstrip('/') + '.json'
    try:
        resp = session.get(json_url, timeout=10)
        if resp.ok:
            data = resp.json()
            product = data.get('product', data)
            text = product.get('title', '') + ' '
            text += product.get('body_html', '') or ''
            text += ' '.join(str(t) for t in product.get('tags', []))
    except:
        pass

    try:
        resp = session.get(url, timeout=10)
        if resp.ok:
            html = resp.text
    except:
        pass

    return html, text


def extract_suitability_data(html, text, product_name):
    """Extract skin types, routine step, and compatibility."""
    content = (html + ' ' + text).lower()
    name_lower = product_name.lower()

    # Extract skin types
    skin_types = set()
    for keyword, skin_name in SKIN_TYPE_KEYWORDS.items():
        if keyword in content:
            skin_types.add(skin_name)

    # Extract routine step (from product name first, then content)
    routine_step = None
    for keyword, step in ROUTINE_STEPS.items():
        if keyword in name_lower:
            routine_step = step
            break
    if not routine_step:
        for keyword, step in ROUTINE_STEPS.items():
            if keyword in content:
                routine_step = step
                break

    # Extract compatibility info
    compatibility = []
    for keyword in COMPATIBILITY_KEYWORDS:
        if keyword in content:
            # Try to extract what follows
            pattern = rf'{keyword}\s+([^.,:]+)'
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches[:2]:  # Limit to 2
                clean = match.strip()[:50]
                if clean and len(clean) > 3:
                    compatibility.append(clean.title())

    return sorted(list(skin_types)), routine_step, compatibility[:3]


def format_suitability(skin_types, routine_step, compatibility):
    """Format all suitability data for display."""
    parts = []

    # Skin types
    if skin_types:
        if len(skin_types) == 1:
            parts.append(f"Skin Type: {skin_types[0]}")
        else:
            parts.append("Skin Types: " + " | ".join(skin_types))

    # Routine step
    if routine_step:
        parts.append(f"Step: {routine_step}")

    # Compatibility
    if compatibility:
        parts.append("Pairs with: " + ", ".join(compatibility))

    return " | ".join(parts)


def update_product(token, item_id, suitability_text, retries=3):
    for attempt in range(retries):
        try:
            data = {
                'isArchived': False,
                'isDraft': False,
                'fieldData': {
                    'suitability-attributes': suitability_text
                }
            }

            resp = requests.patch(
                f'{WEBFLOW_API_BASE}/collections/{PRODUCTS_COLLECTION_ID}/items/{item_id}',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                json=data,
                timeout=30
            )

            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 60))
                print(f'  Rate limited. Waiting {wait}s...')
                time.sleep(wait)
                continue

            return resp.ok
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                return False
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()

    print("=" * 60)
    print("SCRAPE SUITABILITY DATA")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    token = get_webflow_token()

    print("Loading products...")
    products = get_all_items(token, PRODUCTS_COLLECTION_ID)
    print(f"  {len(products)} products")

    # Filter to products without suitability-attributes
    to_process = []
    for p in products:
        fd = p.get('fieldData', {})
        suit_attr = fd.get('suitability-attributes', '').strip()
        url = fd.get('external-link', '')

        if not suit_attr and url:
            to_process.append(p)

    print(f"  {len(to_process)} need scraping")

    if args.limit:
        to_process = to_process[:args.limit]
        print(f"  Limiting to {args.limit}")

    print()

    stats = {
        'processed': 0,
        'found': 0,
        'updated': 0,
        'not_found': 0,
        'errors': 0,
    }

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })

    for i, product in enumerate(to_process, 1):
        fd = product.get('fieldData', {})
        item_id = product.get('id')
        name = fd.get('name', '')
        url = fd.get('external-link', '')

        # Scrape page
        html, text = scrape_product(url, session)

        # Extract suitability data
        skin_types, routine_step, compatibility = extract_suitability_data(html, text, name)

        # Format for display
        suitability_text = format_suitability(skin_types, routine_step, compatibility)

        if suitability_text:
            stats['found'] += 1
            if i <= 20 or i % 50 == 0:
                print(f"[{i}/{len(to_process)}] {name[:40]}")
                print(f"  -> {suitability_text[:70]}")

            if not args.dry_run:
                if update_product(token, item_id, suitability_text):
                    stats['updated'] += 1
                else:
                    stats['errors'] += 1
                time.sleep(0.5)
            else:
                stats['updated'] += 1
        else:
            stats['not_found'] += 1
            if stats['not_found'] <= 10:
                print(f"[{i}/{len(to_process)}] {name[:40]} -> [NOT FOUND]")

        stats['processed'] += 1
        time.sleep(0.3)

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Processed: {stats['processed']}")
    print(f"Found suitability: {stats['found']}")
    print(f"Updated: {stats['updated']}")
    print(f"Not found: {stats['not_found']}")
    print(f"Errors: {stats['errors']}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made.")


if __name__ == '__main__':
    main()
