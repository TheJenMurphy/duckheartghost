#!/usr/bin/env python3
"""
Sync plant-derived ingredient images to Webflow.

This script:
1. Reads the plant_derived_image_matches.json
2. Matches ingredients to Webflow CMS items
3. Updates gallery images for compound ingredients

For images to be uploaded, they must first be hosted (Webflow CDN, Cloudinary, etc.)
This script can:
- Generate a CSV report for manual upload planning
- Update Webflow items with already-hosted image URLs
- Build a mapping of local files to required Webflow uploads

Usage:
    python sync_plant_images_to_webflow.py --report     # Generate CSV report
    python sync_plant_images_to_webflow.py --dry-run    # Show what would be updated
    python sync_plant_images_to_webflow.py --live       # Actually update Webflow
"""

import os
import sys
import json
import csv
import time
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import requests

# Configuration
WEBFLOW_API_BASE = "https://api.webflow.com/v2"
PROJECT_DIR = Path(__file__).parent.parent.parent
MATCHES_FILE = PROJECT_DIR / "plant_derived_image_matches.json"

# Placeholder image
PLACEHOLDER_URL = "https://cdn.prod.website-files.com/6759f0a54f1395fcb6c5b78e/69740e012465c0c53004660b_9s-question-mark.png"

# Webflow gallery image fields (in order)
GALLERY_FIELDS = [
    'hero-image',           # Gallery Image 1 (Hero) - molecular structure or placeholder
    'in-the-field-image',   # Gallery Image 2 (In the Field) - primary plant source
    'gallery-image-3',      # Gallery Image 3
    'gallery-image-4',      # Gallery Image 4
    'gallery-image-5',      # Gallery Image 5
    'gallery-image-6',      # Gallery Image 6
]


class WebflowSyncer:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.collection_id = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')

        if not self.api_token:
            raise ValueError("WEBFLOW_API_TOKEN not set")
        if not self.collection_id:
            raise ValueError("WEBFLOW_INGREDIENTS_COLLECTION_ID not set")

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
        })
        self._last_request = 0
        self._webflow_items = None
        self._name_to_item = {}

    def _rate_limit(self):
        """Respect Webflow rate limits."""
        elapsed = time.time() - self._last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_request = time.time()

    def _request(self, method: str, endpoint: str, json_data=None):
        self._rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'

        try:
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
                print(f'API Error {resp.status_code}: {resp.text[:300]}')
                return None

            return resp.json() if resp.text else {}

        except requests.RequestException as e:
            print(f'Request error: {e}')
            return None

    def load_webflow_ingredients(self):
        """Load all ingredients from Webflow."""
        if self._webflow_items is not None:
            return self._webflow_items

        print("Loading ingredients from Webflow...")
        items = []
        offset = 0
        limit = 100

        while True:
            result = self._request('GET', f'/collections/{self.collection_id}/items?limit={limit}&offset={offset}')
            if not result or not result.get('items'):
                break

            items.extend(result['items'])
            print(f"  Loaded {len(items)} ingredients...", end='\r')

            if len(result['items']) < limit:
                break
            offset += limit

        print(f"  Loaded {len(items)} ingredients total")

        self._webflow_items = items

        # Build name index
        for item in items:
            name = item.get('fieldData', {}).get('name', '')
            if name:
                # Store by normalized name
                normalized = self._normalize_name(name)
                self._name_to_item[normalized] = item

        return items

    def _normalize_name(self, name: str) -> str:
        """Normalize ingredient name for matching."""
        name = name.lower().strip()
        name = re.sub(r'[^a-z0-9\s]', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        return name

    def find_webflow_item(self, ingredient_name: str) -> Optional[Dict]:
        """Find a Webflow item by ingredient name."""
        if not self._webflow_items:
            self.load_webflow_ingredients()

        normalized = self._normalize_name(ingredient_name)
        return self._name_to_item.get(normalized)

    def update_gallery_images(self, item_id: str, images: Dict[str, str]) -> bool:
        """
        Update gallery images for an ingredient.

        Args:
            item_id: Webflow item ID
            images: Dict mapping field slug to image URL
                    e.g., {'hero-image': 'https://...', 'in-the-field-image': 'https://...'}
        """
        field_data = {}
        for field, url in images.items():
            if url:
                field_data[field] = {'url': url}

        if not field_data:
            return False

        data = {'fieldData': field_data}
        result = self._request('PATCH', f'/collections/{self.collection_id}/items/{item_id}', json_data=data)
        return result is not None


def load_matches() -> List[Dict]:
    """Load the plant-derived image matches."""
    if not MATCHES_FILE.exists():
        print(f"Error: Matches file not found: {MATCHES_FILE}")
        print("Run match_plant_derived_images.py first.")
        sys.exit(1)

    with open(MATCHES_FILE) as f:
        return json.load(f)


def generate_report(matches: List[Dict], output_path: Path = None):
    """Generate a CSV report of image mappings for manual review/upload."""
    if output_path is None:
        output_path = PROJECT_DIR / f"plant_image_upload_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    rows = []
    for m in matches:
        if not m.get('source_plants'):
            continue

        row = {
            'ingredient': m['ingredient'],
            'hero_image_url': m.get('hero_image', PLACEHOLDER_URL),
            'source_plants': ', '.join(m.get('source_plants', [])[:6]),
            'num_images_found': len(m.get('all_images', [])),
        }

        # Add individual image paths
        for i, img_path in enumerate(m.get('all_images', [])[:5], 1):
            row[f'local_image_{i}'] = img_path

        rows.append(row)

    # Write CSV
    if rows:
        fieldnames = ['ingredient', 'hero_image_url', 'source_plants', 'num_images_found']
        fieldnames += [f'local_image_{i}' for i in range(1, 6)]

        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"Report saved to: {output_path}")
        print(f"Total ingredients with sources: {len(rows)}")
    else:
        print("No matches with source plants found.")


def sync_to_webflow(matches: List[Dict], dry_run: bool = True):
    """
    Sync image matches to Webflow.

    Note: This only updates hero images (PubChem/placeholder) since gallery images
    require the local files to be uploaded to a CDN first.
    """
    syncer = WebflowSyncer()
    syncer.load_webflow_ingredients()

    print()
    print("=" * 70)
    print("SYNCING TO WEBFLOW")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print()

    # Filter matches with identified sources
    matches_with_sources = [m for m in matches if m.get('source_plants')]
    print(f"Ingredients with identified plant sources: {len(matches_with_sources)}")

    updated = 0
    not_found = 0
    skipped = 0

    for i, match in enumerate(matches_with_sources, 1):
        ingredient_name = match['ingredient']
        hero_url = match.get('hero_image', PLACEHOLDER_URL)

        # Find in Webflow
        wf_item = syncer.find_webflow_item(ingredient_name)

        if not wf_item:
            not_found += 1
            if i <= 20:
                print(f"[{i}] NOT FOUND: {ingredient_name[:50]}")
            continue

        item_id = wf_item['id']
        current_hero = wf_item.get('fieldData', {}).get('hero-image', {})

        # Check if hero already set (and not placeholder)
        if current_hero and current_hero.get('url') and current_hero.get('url') != PLACEHOLDER_URL:
            skipped += 1
            continue

        # Prepare update
        images_to_update = {
            'hero-image': hero_url  # Set PubChem structure or placeholder
        }

        if i <= 20 or i % 100 == 0:
            status = "PubChem" if hero_url != PLACEHOLDER_URL else "Placeholder"
            print(f"[{i}] {ingredient_name[:45]} → {status}")
            print(f"    Sources: {', '.join(match.get('source_plants', [])[:4])}")

        if not dry_run:
            success = syncer.update_gallery_images(item_id, images_to_update)
            if success:
                updated += 1
            else:
                print(f"    FAILED to update")
        else:
            updated += 1

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total with sources: {len(matches_with_sources)}")
    print(f"Would update:       {updated}")
    print(f"Not found in WF:    {not_found}")
    print(f"Skipped (has img):  {skipped}")

    if dry_run:
        print()
        print("[DRY RUN] No changes made.")
        print("Run with --live to apply changes.")
    else:
        print()
        print(f"Successfully updated: {updated}")


def main():
    print("=" * 70)
    print("PLANT-DERIVED INGREDIENT IMAGE SYNC")
    print("=" * 70)
    print()

    # Parse arguments
    args = sys.argv[1:]

    if '--report' in args:
        matches = load_matches()
        generate_report(matches)
        return

    if '--dry-run' in args or '--live' in args:
        matches = load_matches()
        dry_run = '--live' not in args
        sync_to_webflow(matches, dry_run=dry_run)
        return

    # Default: show help
    print(__doc__)
    print()
    print("Quick start:")
    print("  1. Generate report:  python sync_plant_images_to_webflow.py --report")
    print("  2. Dry run:          python sync_plant_images_to_webflow.py --dry-run")
    print("  3. Live update:      python sync_plant_images_to_webflow.py --live")
    print()
    print("Note: Gallery images (in-the-field, etc.) require images to be")
    print("uploaded to a CDN first. Use --report to generate upload list.")


if __name__ == '__main__':
    main()
