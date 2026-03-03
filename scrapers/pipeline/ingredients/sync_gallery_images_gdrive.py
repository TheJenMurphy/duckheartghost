#!/usr/bin/env python3
"""
Sync plant-derived ingredient gallery images to Webflow using Google Drive sharing URLs.

This script:
1. Reads the plant_derived_image_matches.json
2. Maps local image paths to Google Drive paths
3. Extracts Google Drive file IDs from extended attributes
4. Constructs shareable URLs
5. Updates Webflow gallery image fields

Usage:
    python sync_gallery_images_gdrive.py --dry-run    # Show what would be updated
    python sync_gallery_images_gdrive.py --live       # Actually update Webflow
"""

import os
import sys
import json
import time
import re
import subprocess
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

# Local to Google Drive path mapping
LOCAL_MASTER_PATH = Path("/Users/jenmurphy/Downloads/ingredient_images_master")
GDRIVE_MASTER_PATH = Path("/Users/jenmurphy/Library/CloudStorage/GoogleDrive-hello@iheartclean.beauty/My Drive/Ingredient Images/master")

# Google Drive URL format for direct image access
GDRIVE_URL_TEMPLATE = "https://drive.google.com/uc?export=view&id={file_id}"

# Webflow gallery image fields (in order)
GALLERY_FIELDS = [
    'hero-image',           # Gallery Image 1 (Hero) - keep existing
    'in-the-field-image',   # Gallery Image 2 (In the Field) - primary plant source
    'gallery-image-3',      # Gallery Image 3
    'gallery-image-4',      # Gallery Image 4
    'gallery-image-5',      # Gallery Image 5
    'gallery-image-6',      # Gallery Image 6
]


def get_gdrive_file_id(file_path: Path) -> Optional[str]:
    """Extract Google Drive file ID from extended attributes."""
    try:
        # Use xattr -l to list all attrs and find the item-id
        result = subprocess.run(
            ['xattr', '-l', str(file_path)],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            output = result.stdout.decode('utf-8', errors='replace')
            # Look for com.google.drivefs.item-id (may have #S suffix)
            for line in output.split('\n'):
                if 'com.google.drivefs.item-id' in line:
                    # Extract the file ID after the colon
                    parts = line.split(': ', 1)
                    if len(parts) == 2:
                        file_id = parts[1].strip()
                        # Clean up any non-printable or invalid chars
                        file_id = ''.join(c for c in file_id if c.isalnum() or c in '-_')
                        if len(file_id) > 20:
                            return file_id
        return None
    except Exception:
        return None


def local_to_gdrive_path(local_path: str) -> Optional[Path]:
    """Convert local Downloads path to Google Drive path."""
    local_path = Path(local_path)

    # Check if it's in the local master folder
    try:
        relative = local_path.relative_to(LOCAL_MASTER_PATH)
        gdrive_path = GDRIVE_MASTER_PATH / relative
        if gdrive_path.exists():
            return gdrive_path
    except ValueError:
        pass

    # Try matching by folder and filename
    if local_path.exists():
        folder_name = local_path.parent.name
        file_name = local_path.name

        # Look for matching folder in Google Drive
        for gdrive_folder in GDRIVE_MASTER_PATH.iterdir():
            if gdrive_folder.is_dir():
                # Normalize names for comparison
                local_norm = folder_name.lower().replace('_', ' ').replace('-', ' ')
                gdrive_norm = gdrive_folder.name.lower().replace('_', ' ').replace('-', ' ')

                if local_norm == gdrive_norm or local_norm in gdrive_norm or gdrive_norm in local_norm:
                    # Check if file exists
                    gdrive_file = gdrive_folder / file_name
                    if gdrive_file.exists():
                        return gdrive_file

                    # Try with similar filename
                    for gf in gdrive_folder.iterdir():
                        if gf.is_file() and gf.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                            if gf.stem.lower() == local_path.stem.lower():
                                return gf

    return None


def get_gdrive_url(local_path: str) -> Optional[str]:
    """Get Google Drive shareable URL for a local image path."""
    gdrive_path = local_to_gdrive_path(local_path)
    if not gdrive_path:
        return None

    file_id = get_gdrive_file_id(gdrive_path)
    if not file_id:
        return None

    return GDRIVE_URL_TEMPLATE.format(file_id=file_id)


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
        """Update gallery images for an ingredient."""
        field_data = {}
        for field, url in images.items():
            if url:
                field_data[field] = {'url': url}

        if not field_data:
            return False

        data = {
            'isArchived': False,
            'isDraft': False,
            'fieldData': field_data
        }
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


def sync_gallery_to_webflow(matches: List[Dict], dry_run: bool = True):
    """Sync gallery images to Webflow using Google Drive URLs."""
    syncer = WebflowSyncer()
    syncer.load_webflow_ingredients()

    print()
    print("=" * 70)
    print("SYNCING GALLERY IMAGES TO WEBFLOW (Google Drive)")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print()

    # Filter matches with identified sources and images
    matches_with_images = [m for m in matches if m.get('all_images')]
    print(f"Ingredients with matched images: {len(matches_with_images)}")
    print()

    # First, test Google Drive URL conversion
    print("Testing Google Drive URL conversion...")
    test_count = 0
    for m in matches_with_images[:10]:
        for img_path in m.get('all_images', [])[:1]:
            url = get_gdrive_url(img_path)
            if url:
                test_count += 1
                print(f"  OK: {Path(img_path).name[:40]} → URL generated")
            else:
                print(f"  FAIL: {Path(img_path).name[:40]} → No Google Drive match")
    print(f"  Test result: {test_count}/10 images have Google Drive URLs")
    print()

    if test_count == 0:
        print("ERROR: Could not generate any Google Drive URLs.")
        print("Make sure the images are synced to Google Drive.")
        return

    updated = 0
    not_found = 0
    no_urls = 0
    skipped = 0

    for i, match in enumerate(matches_with_images, 1):
        ingredient_name = match['ingredient']
        local_images = match.get('all_images', [])[:5]  # Up to 5 gallery images

        # Find in Webflow
        wf_item = syncer.find_webflow_item(ingredient_name)

        if not wf_item:
            not_found += 1
            continue

        item_id = wf_item['id']
        field_data = wf_item.get('fieldData', {})

        # Check if gallery images already set
        has_gallery = field_data.get('in-the-field-image') and field_data['in-the-field-image'].get('url')
        if has_gallery:
            skipped += 1
            continue

        # Convert local paths to Google Drive URLs
        gallery_updates = {}
        gallery_fields_to_use = ['in-the-field-image', 'gallery-image-3', 'gallery-image-4', 'gallery-image-5', 'gallery-image-6']

        urls_found = 0
        for j, local_path in enumerate(local_images):
            if j >= len(gallery_fields_to_use):
                break

            url = get_gdrive_url(local_path)
            if url:
                gallery_updates[gallery_fields_to_use[j]] = url
                urls_found += 1

        if not gallery_updates:
            no_urls += 1
            continue

        if i <= 30 or i % 100 == 0:
            print(f"[{i}] {ingredient_name[:45]}")
            print(f"    Sources: {', '.join(match.get('source_plants', [])[:4])}")
            print(f"    Gallery images: {urls_found}")

        if not dry_run:
            success = syncer.update_gallery_images(item_id, gallery_updates)
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
    print(f"Total with images:  {len(matches_with_images)}")
    print(f"Would update:       {updated}")
    print(f"Not found in WF:    {not_found}")
    print(f"No Google Drive URL:{no_urls}")
    print(f"Skipped (has imgs): {skipped}")

    if dry_run:
        print()
        print("[DRY RUN] No changes made.")
        print("Run with --live to apply changes.")
    else:
        print()
        print(f"Successfully updated: {updated}")


def main():
    print("=" * 70)
    print("PLANT-DERIVED GALLERY IMAGES → WEBFLOW (Google Drive)")
    print("=" * 70)
    print()

    # Check Google Drive folder exists
    if not GDRIVE_MASTER_PATH.exists():
        print(f"ERROR: Google Drive master folder not found:")
        print(f"  {GDRIVE_MASTER_PATH}")
        print()
        print("Make sure Google Drive is synced and the path is correct.")
        sys.exit(1)

    # Parse arguments
    args = sys.argv[1:]

    if '--dry-run' in args or '--live' in args:
        matches = load_matches()
        dry_run = '--live' not in args
        sync_gallery_to_webflow(matches, dry_run=dry_run)
        return

    # Default: show help
    print(__doc__)
    print()
    print("Quick start:")
    print("  1. Dry run:     python sync_gallery_images_gdrive.py --dry-run")
    print("  2. Live update: python sync_gallery_images_gdrive.py --live")


if __name__ == '__main__':
    main()
