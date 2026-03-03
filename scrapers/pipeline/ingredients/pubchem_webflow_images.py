#!/usr/bin/env python3
"""
Fetch PubChem molecule images for Webflow ingredients.

Scrapes PubChem for molecular structure images and updates Webflow CMS
hero-image field for synthetic and plant-derived synthetic ingredients.
"""

import os
import json
import time
import requests
from pathlib import Path
from typing import Optional, List, Dict
from urllib.parse import quote

# Load .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# API Configuration
WEBFLOW_API_TOKEN = os.environ.get('WEBFLOW_API_TOKEN', '')
WEBFLOW_INGREDIENTS_COLLECTION_ID = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')
PUBCHEM_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

HEADERS = {
    'User-Agent': 'iHeartClean-Bot/1.0 (ingredient research)'
}


def get_pubchem_cid(ingredient_name: str, cas_number: str = None) -> Optional[int]:
    """
    Search PubChem for compound CID.
    Tries CAS number first, then name.
    """
    cid = None

    # Try CAS number first (most reliable)
    if cas_number:
        try:
            url = f"{PUBCHEM_API}/compound/name/{quote(cas_number)}/cids/JSON"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                cids = data.get('IdentifierList', {}).get('CID', [])
                if cids:
                    return cids[0]
        except Exception:
            pass

    # Try ingredient name
    if not cid:
        # Clean up name for search
        search_name = ingredient_name
        # Remove parenthetical parts for cleaner search
        import re
        search_name = re.sub(r'\s*\([^)]*\)\s*', ' ', search_name).strip()

        if search_name:
            try:
                url = f"{PUBCHEM_API}/compound/name/{quote(search_name)}/cids/JSON"
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    cids = data.get('IdentifierList', {}).get('CID', [])
                    if cids:
                        return cids[0]
            except Exception:
                pass

    return None


def get_pubchem_image_url(cid: int, size: int = 500) -> str:
    """Generate PubChem image URL for a compound CID."""
    return f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG?image_size={size}x{size}"


def fetch_webflow_ingredients(ingredient_type: str = None, missing_images_only: bool = True) -> List[Dict]:
    """
    Fetch ingredients from Webflow CMS.

    Args:
        ingredient_type: 'synthetic' or 'plant-derived' or None for all
        missing_images_only: Only return items without hero-image

    Returns:
        List of ingredient dicts with id, name, slug, cas, type fields
    """
    if not WEBFLOW_API_TOKEN or not WEBFLOW_INGREDIENTS_COLLECTION_ID:
        print("Error: Missing WEBFLOW_API_TOKEN or WEBFLOW_INGREDIENTS_COLLECTION_ID")
        return []

    headers = {
        'Authorization': f'Bearer {WEBFLOW_API_TOKEN}',
        'Content-Type': 'application/json'
    }

    all_items = []
    offset = 0
    limit = 100

    print(f"Fetching ingredients from Webflow...")

    while True:
        url = f"https://api.webflow.com/v2/collections/{WEBFLOW_INGREDIENTS_COLLECTION_ID}/items?limit={limit}&offset={offset}"
        resp = requests.get(url, headers=headers)

        if resp.status_code != 200:
            print(f"Error fetching Webflow: {resp.status_code}")
            break

        data = resp.json()
        items = data.get('items', [])

        for item in items:
            fd = item.get('fieldData', {})

            # Get type
            item_type = fd.get('type-i-e-mineral-vitamin-botanical-synthetic-plant-derived-synthetic', '').lower()

            # Filter by type if specified
            if ingredient_type:
                if ingredient_type == 'synthetic' and item_type != 'synthetic':
                    continue
                if ingredient_type == 'plant-derived' and item_type != 'plant-derived':
                    continue

            # Check if missing hero image
            has_hero = fd.get('hero-image') is not None
            if missing_images_only and has_hero:
                continue

            all_items.append({
                'id': item.get('id'),
                'name': fd.get('name', ''),
                'slug': fd.get('slug', ''),
                'cas': fd.get('cas-2', ''),
                'type': item_type,
                'has_hero': has_hero
            })

        total = data.get('pagination', {}).get('total', 0)
        offset += limit

        if offset % 500 == 0:
            print(f"  Fetched {len(all_items)} matching items ({offset} scanned)...")

        if len(items) < limit or offset >= total:
            break

        time.sleep(0.1)  # Small delay

    print(f"Found {len(all_items)} ingredients matching criteria")
    return all_items


def update_webflow_hero_image(item_id: str, image_url: str) -> bool:
    """Update hero-image field in Webflow."""
    if not WEBFLOW_API_TOKEN:
        return False

    headers = {
        'Authorization': f'Bearer {WEBFLOW_API_TOKEN}',
        'Content-Type': 'application/json'
    }

    url = f"https://api.webflow.com/v2/collections/{WEBFLOW_INGREDIENTS_COLLECTION_ID}/items/{item_id}"

    data = {
        'fieldData': {
            'hero-image': {'url': image_url}
        }
    }

    try:
        resp = requests.patch(url, headers=headers, json=data)
        return resp.status_code == 200
    except Exception as e:
        print(f"Error updating Webflow: {e}")
        return False


def scrape_pubchem_images(ingredient_type: str = 'synthetic', limit: int = None, dry_run: bool = False):
    """
    Main function to scrape PubChem images and update Webflow.

    Args:
        ingredient_type: 'synthetic' or 'plant-derived'
        limit: Max ingredients to process (None for all)
        dry_run: If True, don't actually update Webflow
    """
    print(f"\n{'='*60}")
    print(f"PubChem Image Scraper for Webflow")
    print(f"{'='*60}")
    print(f"Type: {ingredient_type}")
    print(f"Limit: {limit or 'all'}")
    print(f"Dry run: {dry_run}")
    print()

    # Fetch ingredients
    ingredients = fetch_webflow_ingredients(
        ingredient_type=ingredient_type,
        missing_images_only=True
    )

    if limit:
        ingredients = ingredients[:limit]

    total = len(ingredients)
    print(f"\nProcessing {total} ingredients...\n")

    stats = {
        'total': total,
        'found': 0,
        'not_found': 0,
        'updated': 0,
        'failed': 0
    }

    for i, ing in enumerate(ingredients, 1):
        name = ing['name']
        cas = ing['cas']
        item_id = ing['id']

        # Search PubChem
        cid = get_pubchem_cid(name, cas)

        if cid:
            image_url = get_pubchem_image_url(cid)
            stats['found'] += 1

            if dry_run:
                print(f"[{i}/{total}] ✓ {name} -> CID {cid}")
            else:
                # Update Webflow
                if update_webflow_hero_image(item_id, image_url):
                    stats['updated'] += 1
                    print(f"[{i}/{total}] ✓ {name} -> CID {cid} (updated)")
                else:
                    stats['failed'] += 1
                    print(f"[{i}/{total}] ✓ {name} -> CID {cid} (update failed)")
        else:
            stats['not_found'] += 1
            if i <= 20 or i % 100 == 0:  # Only print first 20 and every 100th
                print(f"[{i}/{total}] ✗ {name} (not found)")

        # Rate limiting - PubChem allows 5 req/sec, Webflow 60/min
        time.sleep(0.3)

        # Progress update every 100
        if i % 100 == 0:
            print(f"\n--- Progress: {i}/{total} | Found: {stats['found']} | Not found: {stats['not_found']} ---\n")

    # Final report
    print(f"\n{'='*60}")
    print("COMPLETE")
    print(f"{'='*60}")
    print(f"Total processed: {stats['total']}")
    print(f"Found in PubChem: {stats['found']} ({stats['found']/stats['total']*100:.1f}%)")
    print(f"Not found: {stats['not_found']} ({stats['not_found']/stats['total']*100:.1f}%)")
    if not dry_run:
        print(f"Updated in Webflow: {stats['updated']}")
        print(f"Update failed: {stats['failed']}")

    return stats


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Scrape PubChem images for Webflow ingredients')
    parser.add_argument('--type', choices=['synthetic', 'plant-derived', 'both'],
                        default='both', help='Ingredient type to process')
    parser.add_argument('--limit', type=int, help='Max ingredients to process')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t update Webflow')

    args = parser.parse_args()

    if args.type == 'both':
        print("\n" + "="*60)
        print("Processing SYNTHETIC ingredients")
        print("="*60)
        scrape_pubchem_images('synthetic', limit=args.limit, dry_run=args.dry_run)

        print("\n" + "="*60)
        print("Processing PLANT-DERIVED SYNTHETIC ingredients")
        print("="*60)
        scrape_pubchem_images('plant-derived', limit=args.limit, dry_run=args.dry_run)
    else:
        scrape_pubchem_images(args.type, limit=args.limit, dry_run=args.dry_run)
