#!/usr/bin/env python3
"""
Scrape benefits and skin types from product pages.

Usage:
    python scrape_benefits_skintypes.py --dry-run --limit 50
    python scrape_benefits_skintypes.py
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
BENEFITS_COLLECTION_ID = "69929088341dfe9991b033f1"
SKIN_TYPES_COLLECTION_ID = "699283e31127be0de2d6552c"

# Benefits keywords to look for
BENEFITS_KEYWORDS = {
    'hydrating': 'hydrating',
    'hydration': 'hydrating',
    'hyaluronic': 'hydrating',
    'moisturizing': 'moisturizing',
    'moisturize': 'moisturizing',
    'moisture': 'moisturizing',
    'emollient': 'moisturizing',
    'brightening': 'brightening',
    'brighten': 'brightening',
    'luminous': 'brightening',
    'radiance': 'radiance-boosting',
    'radiant': 'radiance-boosting',
    'glow': 'radiance-boosting',
    'illuminat': 'radiance-boosting',
    'firming': 'firming',
    'firm': 'firming',
    'tighten': 'firming',
    'lift': 'firming',
    'smoothing': 'smoothing',
    'smooth': 'smoothing',
    'silky': 'smoothing',
    'soothing': 'soothing',
    'soothe': 'soothing',
    'comfort': 'soothing',
    'calming': 'calming',
    'calm': 'calming',
    'anti-aging': 'antiaging',
    'anti aging': 'antiaging',
    'antiaging': 'antiaging',
    'youthful': 'antiaging',
    'wrinkle': 'line-reducing',
    'fine lines': 'line-reducing',
    'line-reducing': 'line-reducing',
    'plumping': 'plumping',
    'plump': 'plumping',
    'nourishing': 'nourishing',
    'nourish': 'nourishing',
    'nutrient': 'nourishing',
    'vitamin': 'nourishing',
    'softening': 'softening',
    'soften': 'softening',
    'soft': 'softening',
    'silken': 'softening',
    'exfoliating': 'exfoliating',
    'exfoliate': 'exfoliating',
    'resurfacing': 'resurfacing',
    'resurface': 'resurfacing',
    'renew': 'resurfacing',
    'antioxidant': 'antioxidant',
    'vitamin c': 'antioxidant',
    'vitamin e': 'antioxidant',
    'protect': 'antioxidant',
    'acne': 'acne-fighting',
    'blemish': 'acne-fighting',
    'breakout': 'acne-fighting',
    'clarifying': 'clarifying',
    'clarify': 'clarifying',
    'cleanse': 'clarifying',
    'clean': 'clarifying',
    'pore': 'pore minimizing',
    'oil control': 'oil-controlling',
    'oil-control': 'oil-controlling',
    'mattifying': 'oil-controlling',
    'matte': 'oil-controlling',
    'healing': 'healing',
    'repair': 'healing',
    'restore': 'healing',
    'regenerat': 'healing',
    'redness': 'redness-reducing',
    'rosacea': 'redness-reducing',
    'dark spot': 'dark-spot correcting',
    'hyperpigmentation': 'dark-spot correcting',
    'discoloration': 'dark-spot correcting',
    'even tone': 'tone-evening',
    'tone evening': 'tone-evening',
    'even skin': 'tone-evening',
    'uv protect': 'uv-protecting',
    'sun protect': 'uv-protecting',
    'spf': 'uv-protecting',
    'broad spectrum': 'uv-protecting',
    'pollution': 'pollution-protecting',
    'barrier': 'barrier-strengthening',
    'strengthen': 'barrier-strengthening',
    'blurring': 'blurring',
    'blur': 'blurring',
    'perfect': 'blurring',
    'coverage': 'blurring',
    'volumiz': 'plumping',
    'volume': 'plumping',
    'fullness': 'plumping',
    'shine': 'radiance-boosting',
    'peptide': 'firming',
    'collagen': 'firming',
    'elastin': 'firming',
    'ceramide': 'barrier-strengthening',
    'omega': 'nourishing',
}

# Skin type keywords
SKIN_TYPE_KEYWORDS = {
    'all skin': 'all skin',
    'all skin types': 'all skin',
    'universal': 'all skin',
    'every skin': 'all skin',
    'any skin': 'all skin',
    'suitable for all': 'all skin',
    'for everyone': 'all skin',
    'dry skin': 'dry',
    'dry': 'dry',
    'parched': 'dry',
    'oily skin': 'oily',
    'oily': 'oily',
    'excess oil': 'oily',
    'combination skin': 'combination',
    'combination': 'combination',
    'sensitive skin': 'sensitive',
    'sensitive': 'sensitive',
    'gentle': 'sensitive',
    'fragile': 'sensitive',
    'reactive': 'sensitive',
    'acne-prone': 'acne-prone',
    'acne prone': 'acne-prone',
    'breakout': 'acne-prone',
    'blemish-prone': 'acne-prone',
    'dehydrated': 'dehydrated',
    'thirsty skin': 'dehydrated',
    'melanin-rich': 'melanin-rich',
    'melanin rich': 'melanin-rich',
    'dark skin': 'melanin-rich',
    'normal skin': 'all skin',
    'normal': 'all skin',
    'mature skin': 'all skin',
    'aging skin': 'all skin',
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


def build_lookup(items):
    lookup = {}
    for item in items:
        fd = item.get('fieldData', {})
        name = fd.get('name', '').strip().lower()
        if name:
            lookup[name] = item.get('id')
            lookup[name.replace('-', ' ')] = item.get('id')
            lookup[name.replace('-', '')] = item.get('id')
            lookup[name.replace(' ', '-')] = item.get('id')
    return lookup


def extract_from_page(html, text, benefits_lookup, skin_lookup):
    """Extract benefits and skin types from page content."""
    content = (html + ' ' + text).lower()

    benefits_found = set()
    skin_found = set()

    # Look for benefits
    for keyword, benefit_name in BENEFITS_KEYWORDS.items():
        if keyword in content:
            benefit_id = benefits_lookup.get(benefit_name)
            if benefit_id:
                benefits_found.add(benefit_id)

    # Look for skin types
    for keyword, skin_name in SKIN_TYPE_KEYWORDS.items():
        if keyword in content:
            skin_id = skin_lookup.get(skin_name)
            if skin_id:
                skin_found.add(skin_id)

    # If we found benefits but no skin types, default to "all skin"
    if benefits_found and not skin_found:
        all_skin_id = skin_lookup.get('all skin')
        if all_skin_id:
            skin_found.add(all_skin_id)

    return list(benefits_found), list(skin_found)


def scrape_product(url, session):
    """Scrape a product page."""
    # Try Shopify JSON first
    json_url = url.rstrip('/') + '.json'
    html = ''
    text = ''

    try:
        resp = session.get(json_url, timeout=10)
        if resp.ok:
            data = resp.json()
            product = data.get('product', data)
            text = product.get('title', '') + ' '
            text += product.get('body_html', '') or ''
            text += ' '.join(t.get('name', '') for t in product.get('tags', []))
            # Get variant info
            for v in product.get('variants', []):
                text += ' ' + v.get('title', '')
    except:
        pass

    # Also get HTML page
    try:
        resp = session.get(url, timeout=10)
        if resp.ok:
            html = resp.text
    except:
        pass

    return html, text


def update_product(token, item_id, benefits_ids, skin_ids, retries=3):
    for attempt in range(retries):
        try:
            data = {
                'isArchived': False,
                'isDraft': False,
                'fieldData': {}
            }

            if benefits_ids:
                data['fieldData']['benefits'] = benefits_ids[:25]
            if skin_ids:
                data['fieldData']['skin-types-2'] = skin_ids[:25]

            if not data['fieldData']:
                return True

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
    print("SCRAPE BENEFITS & SKIN TYPES")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    token = get_webflow_token()

    # Load reference collections
    print("Loading Benefits collection...")
    benefits_items = get_all_items(token, BENEFITS_COLLECTION_ID)
    benefits_lookup = build_lookup(benefits_items)
    print(f"  {len(benefits_items)} benefits")

    print("Loading Skin Types collection...")
    skin_items = get_all_items(token, SKIN_TYPES_COLLECTION_ID)
    skin_lookup = build_lookup(skin_items)
    print(f"  {len(skin_items)} skin types")

    print("Loading products...")
    products = get_all_items(token, PRODUCTS_COLLECTION_ID)
    print(f"  {len(products)} products")

    # Filter to products without refs
    to_process = []
    for p in products:
        fd = p.get('fieldData', {})
        url = fd.get('external-link', '')
        benefits_ref = fd.get('benefits', []) or []
        skin_ref = fd.get('skin-types-2', []) or []

        if url and (not benefits_ref or not skin_ref):
            to_process.append(p)

    print(f"  {len(to_process)} need scraping")

    if args.limit:
        to_process = to_process[:args.limit]
        print(f"  Limiting to {args.limit}")

    print()

    stats = {
        'processed': 0,
        'updated': 0,
        'benefits_found': 0,
        'skin_found': 0,
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

        existing_benefits = fd.get('benefits', []) or []
        existing_skin = fd.get('skin-types-2', []) or []

        # Scrape page
        html, text = scrape_product(url, session)

        # Extract benefits and skin types
        benefits_ids, skin_ids = extract_from_page(html, text, benefits_lookup, skin_lookup)

        # Merge with existing
        if existing_benefits:
            benefits_ids = list(set(existing_benefits + benefits_ids))
        if existing_skin:
            skin_ids = list(set(existing_skin + skin_ids))

        new_benefits = len(benefits_ids) - len(existing_benefits)
        new_skin = len(skin_ids) - len(existing_skin)

        if new_benefits > 0:
            stats['benefits_found'] += 1
        if new_skin > 0:
            stats['skin_found'] += 1

        if i <= 20 or i % 100 == 0:
            print(f"[{i}/{len(to_process)}] {name[:40]}")
            if new_benefits > 0:
                print(f"  +{new_benefits} benefits")
            if new_skin > 0:
                print(f"  +{new_skin} skin types")

        if new_benefits > 0 or new_skin > 0:
            if not args.dry_run:
                if update_product(token, item_id, benefits_ids if new_benefits else None,
                                  skin_ids if new_skin else None):
                    stats['updated'] += 1
                else:
                    stats['errors'] += 1
                time.sleep(0.5)
            else:
                stats['updated'] += 1

        stats['processed'] += 1
        time.sleep(0.3)  # Rate limit scraping

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Processed: {stats['processed']}")
    print(f"Updated: {stats['updated']}")
    print(f"Products with new benefits: {stats['benefits_found']}")
    print(f"Products with new skin types: {stats['skin_found']}")
    print(f"Errors: {stats['errors']}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made.")


if __name__ == '__main__':
    main()
