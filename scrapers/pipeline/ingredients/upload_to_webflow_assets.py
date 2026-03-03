"""
Upload ingredient images directly to Webflow Assets and update CMS items.

This uses the Webflow Assets API to:
1. Create asset metadata (get pre-signed S3 upload URL)
2. Upload image to S3
3. Update CMS item with the Webflow-hosted URL
"""

import os
import sys
import time
import hashlib
import re
from pathlib import Path
from difflib import SequenceMatcher

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import requests

WEBFLOW_API_BASE = "https://api.webflow.com/v2"
LOCAL_IMAGES_DIR = os.path.expanduser("~/Downloads/ingredient_images_master")

# Image field slugs in order of priority
IMAGE_FIELDS = [
    'hero-image',
    'in-the-field-image',
    'gallery-image-3',
    'gallery-image-4',
    'gallery-image-5',
    'gallery-image-6',
]


def normalize_name(name):
    """Normalize ingredient name for matching."""
    name = re.sub(r'\.(jpg|jpeg|png|gif|webp)$', '', name, flags=re.IGNORECASE)
    name = name.strip().lower()
    name = name.replace('_', ' ')
    name = re.sub(r'\s+', ' ', name)
    return name


def clean_for_matching(name):
    """Clean name for fuzzy matching."""
    name = normalize_name(name)
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'\[^]]*\]', '', name)
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def similarity(a, b):
    """Calculate similarity ratio."""
    return SequenceMatcher(None, a, b).ratio()


def is_junk_name(name):
    """Check if ingredient name is junk."""
    junk = {'ext', 'pharmaceutical secondary standard', '1', '2', '3', '3s', 'powder', 'puriss'}
    normalized = normalize_name(name)
    if normalized in junk:
        return True
    if len(normalized) <= 3:
        return True
    if normalized.startswith('●'):
        return True
    return False


def classify_image(filename):
    """Classify image type based on filename."""
    lower = filename.lower()

    # Hero indicators
    hero_patterns = ['on white', 'white background', 'transparent', 'isolated',
                     'studio', 'product shot', 'cutout', 'hero_', 'hero-',
                     'clean background', 'white bg', 'pure white', 'square']
    for pattern in hero_patterns:
        if pattern in lower:
            return 'hero'

    # Field indicators
    field_patterns = ['field', 'branch', 'plant', 'tree', 'growing', 'farm',
                      'nature', 'outdoor', 'wild', 'garden', 'field_', 'field-']
    for pattern in field_patterns:
        if pattern in lower:
            return 'field'

    return 'other'


def get_content_type(filename):
    """Get content type from filename."""
    ext = filename.lower().split('.')[-1]
    types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp',
    }
    return types.get(ext, 'image/jpeg')


class WebflowImageUploader:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.collection_id = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')
        self.site_id = os.environ.get('WEBFLOW_SITE_ID', '')

        if not all([self.api_token, self.collection_id, self.site_id]):
            raise ValueError("Missing WEBFLOW_API_TOKEN, WEBFLOW_INGREDIENTS_COLLECTION_ID, or WEBFLOW_SITE_ID")

        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        # Cache of uploaded assets to avoid duplicates
        self.uploaded_assets = {}

    def upload_image_to_assets(self, file_path, display_name=None):
        """Upload an image to Webflow Assets and return the hosted URL."""
        if file_path in self.uploaded_assets:
            return self.uploaded_assets[file_path]

        with open(file_path, 'rb') as f:
            file_content = f.read()

        file_hash = hashlib.md5(file_content).hexdigest()
        filename = display_name or os.path.basename(file_path)
        content_type = get_content_type(filename)

        # Step 1: Create asset metadata
        resp = requests.post(
            f'{WEBFLOW_API_BASE}/sites/{self.site_id}/assets',
            headers=self.headers,
            json={
                'fileName': filename,
                'fileHash': file_hash
            }
        )

        if resp.status_code == 409:
            # Asset with same hash already exists, check response for URL
            data = resp.json()
            if 'hostedUrl' in data:
                self.uploaded_assets[file_path] = data['hostedUrl']
                return data['hostedUrl']
            return None

        if not resp.ok:
            return None

        data = resp.json()
        upload_url = data['uploadUrl']
        upload_details = data['uploadDetails']
        hosted_url = data['hostedUrl']

        # Step 2: Upload to S3
        form_data = {
            'acl': upload_details['acl'],
            'bucket': upload_details['bucket'],
            'X-Amz-Algorithm': upload_details['X-Amz-Algorithm'],
            'X-Amz-Credential': upload_details['X-Amz-Credential'],
            'X-Amz-Date': upload_details['X-Amz-Date'],
            'key': upload_details['key'],
            'Policy': upload_details['Policy'],
            'X-Amz-Signature': upload_details['X-Amz-Signature'],
            'success_action_status': upload_details['success_action_status'],
            'Content-Type': upload_details.get('content-type', content_type),
            'Cache-Control': upload_details['Cache-Control'],
        }

        resp = requests.post(
            upload_url,
            data=form_data,
            files={'file': (filename, file_content, content_type)}
        )

        if resp.status_code == 201:
            self.uploaded_assets[file_path] = hosted_url
            return hosted_url

        return None

    def get_all_ingredients(self):
        """Fetch all ingredients from Webflow."""
        items = []
        offset = 0
        limit = 100

        while True:
            resp = requests.get(
                f'{WEBFLOW_API_BASE}/collections/{self.collection_id}/items',
                headers=self.headers,
                params={'offset': offset, 'limit': limit}
            )
            if not resp.ok:
                print(f"Error fetching: {resp.status_code}")
                break

            data = resp.json()
            batch = data.get('items', [])
            items.extend(batch)

            if len(batch) < limit:
                break
            offset += limit
            if offset % 1000 == 0:
                print(f"  Fetched {offset}...")
            time.sleep(0.1)

        return items

    def update_item_images(self, item_id, image_urls, dry_run=True):
        """Update item with image URLs."""
        field_data = {}

        slot_to_field = {
            'hero': 'hero-image',
            'field': 'in-the-field-image',
            'g3': 'gallery-image-3',
            'g4': 'gallery-image-4',
            'g5': 'gallery-image-5',
            'g6': 'gallery-image-6',
        }

        for slot, url in image_urls.items():
            field = slot_to_field.get(slot)
            if field and url:
                field_data[field] = {'url': url}

        if not field_data:
            return False

        if dry_run:
            return True

        resp = requests.patch(
            f'{WEBFLOW_API_BASE}/collections/{self.collection_id}/items/{item_id}',
            headers=self.headers,
            json={'fieldData': field_data}
        )

        return resp.ok

    def list_local_folders(self):
        """List all ingredient folders in local directory."""
        folders = []
        for item in os.listdir(LOCAL_IMAGES_DIR):
            path = os.path.join(LOCAL_IMAGES_DIR, item)
            if os.path.isdir(path):
                folders.append(item)
        return sorted(folders)

    def list_folder_images(self, folder_name):
        """List images in a folder."""
        images = []
        folder_path = os.path.join(LOCAL_IMAGES_DIR, folder_name)
        for item in os.listdir(folder_path):
            if item.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                images.append({
                    'name': item,
                    'path': os.path.join(folder_path, item),
                    'size': os.path.getsize(os.path.join(folder_path, item))
                })
        return images

    def pick_best_images(self, images, max_images=6):
        """Pick best images for each slot."""
        result = {}

        # Classify all images
        classified = {'hero': [], 'field': [], 'other': []}
        for img in images:
            img_type = classify_image(img.get('name', ''))
            classified[img_type].append(img)

        # Sort each category by size (larger = better quality)
        for cat in classified:
            classified[cat].sort(key=lambda x: x.get('size', 0), reverse=True)

        used = set()

        # Assign hero
        for img in classified['hero']:
            if img['path'] not in used:
                result['hero'] = img
                used.add(img['path'])
                break

        # Assign field
        for img in classified['field']:
            if img['path'] not in used:
                result['field'] = img
                used.add(img['path'])
                break

        # Fill remaining slots with other images
        all_remaining = [img for cat in ['other', 'hero', 'field']
                         for img in classified[cat] if img['path'] not in used]

        for slot in ['g3', 'g4', 'g5', 'g6']:
            if all_remaining:
                img = all_remaining.pop(0)
                result[slot] = img
                used.add(img['path'])

        return result

    def process(self, dry_run=True, limit=None):
        """Process all folders and upload to Webflow."""
        print("=" * 60)
        print("WEBFLOW DIRECT IMAGE UPLOADER")
        print("=" * 60)
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPLOAD'}")
        print()

        # Get local folders
        print("Scanning local image folders...")
        folders = self.list_local_folders()
        print(f"Found {len(folders)} ingredient folders")

        if not folders:
            print("No folders found.")
            return

        # Get Webflow ingredients
        print("\nFetching Webflow ingredients...")
        items = self.get_all_ingredients()
        print(f"Found {len(items)} Webflow ingredients")

        # Build indices
        exact_index = {}
        clean_index = {}
        for item in items:
            name = item.get('fieldData', {}).get('name', '')
            if name and not is_junk_name(name):
                exact_index[normalize_name(name)] = item
                clean_index[clean_for_matching(name)] = item

        # Process folders
        matched = 0
        updated = 0
        uploaded_images = 0

        for i, folder_name in enumerate(folders):
            if limit and i >= limit:
                break

            # Find matching Webflow item
            normalized = normalize_name(folder_name)
            cleaned = clean_for_matching(folder_name)

            item = exact_index.get(normalized) or clean_index.get(cleaned)

            # Try similarity matching
            if not item:
                best_score = 0
                for name, candidate in exact_index.items():
                    score = similarity(normalized, name)
                    if score > best_score and score > 0.85:
                        best_score = score
                        item = candidate

            if not item:
                continue

            matched += 1
            item_name = item.get('fieldData', {}).get('name', '')
            item_id = item.get('id', '')

            # Get images in folder
            images = self.list_folder_images(folder_name)
            if not images:
                continue

            # Pick best images
            best = self.pick_best_images(images)

            if dry_run:
                print(f"\n[{matched}] {folder_name} -> {item_name}")
                print(f"  Would upload: {list(best.keys())}")
                continue

            # Upload images and get URLs
            print(f"[{matched}] {item_name}...", end=' ', flush=True)

            image_urls = {}
            for slot, img in best.items():
                # Create a clean filename for Webflow
                clean_name = f"{normalized.replace(' ', '-')}_{slot}.{img['name'].split('.')[-1]}"
                url = self.upload_image_to_assets(img['path'], clean_name)
                if url:
                    image_urls[slot] = url
                    uploaded_images += 1
                time.sleep(0.2)  # Rate limiting

            if not image_urls:
                print("no images uploaded")
                continue

            # Update CMS item
            success = self.update_item_images(item_id, image_urls, dry_run=False)
            if success:
                updated += 1
                print(f"OK ({len(image_urls)} images)")
            else:
                print("CMS update FAILED")

            time.sleep(0.3)  # Rate limiting

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Local folders:    {len(folders)}")
        print(f"Matched:          {matched}")
        if not dry_run:
            print(f"Images uploaded:  {uploaded_images}")
            print(f"Items updated:    {updated}")

        if dry_run:
            print("\nTo upload, run:")
            print("  python3 upload_to_webflow_assets.py --upload")


def main():
    dry_run = '--upload' not in sys.argv
    limit = None
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    uploader = WebflowImageUploader()
    uploader.process(dry_run=dry_run, limit=limit)


if __name__ == '__main__':
    main()
