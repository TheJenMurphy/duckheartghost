"""
Upload ingredient images to Webflow Assets and link to ingredients.

Uses Webflow's v2 API to:
1. Upload images to Webflow's asset CDN
2. Update ingredient items with the image URLs
"""

import os
import sys
import time
import re
import mimetypes
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
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def similarity(a, b):
    """Calculate similarity ratio."""
    return SequenceMatcher(None, a, b).ratio()


# Junk names to skip
JUNK_NAMES = {
    'ext', 'pharmaceutical secondary standard', '●  oils', '● oils',
    '1', '2', '3', '3s', '4aa', 'pharmagrade', 'powder', 'mixture of isomers',
    'puriss', 'beantree', '959610-30-1', '●  titanium(iv) oxide',
}


def is_junk_name(name):
    """Check if a name is junk."""
    normalized = normalize_name(name)
    if normalized in JUNK_NAMES:
        return True
    if len(normalized) <= 3:
        return True
    if re.match(r'^[\d\-]+$', normalized):
        return True
    if normalized.startswith('●'):
        return True
    return False


class WebflowAssetUploader:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.site_id = os.environ.get('WEBFLOW_SITE_ID', '')
        self.collection_id = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')

        if not self.api_token:
            raise ValueError("WEBFLOW_API_TOKEN not set")
        if not self.site_id:
            raise ValueError("WEBFLOW_SITE_ID not set")
        if not self.collection_id:
            raise ValueError("WEBFLOW_INGREDIENTS_COLLECTION_ID not set")

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
        })
        self._last_request = 0

    def _rate_limit(self, min_delay=0.5):
        elapsed = time.time() - self._last_request
        if elapsed < min_delay:
            time.sleep(min_delay - elapsed)
        self._last_request = time.time()

    def _request(self, method: str, endpoint: str, json_data=None, data=None, files=None, headers=None):
        self._rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'

        req_headers = dict(self.session.headers)
        if headers:
            req_headers.update(headers)

        try:
            if files:
                # Remove content-type for multipart
                req_headers.pop('Content-Type', None)
                resp = requests.request(method, url, data=data, files=files, headers=req_headers)
            elif json_data:
                req_headers['Content-Type'] = 'application/json'
                resp = requests.request(method, url, json=json_data, headers=req_headers)
            else:
                resp = requests.request(method, url, headers=req_headers)

            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 60))
                print(f'Rate limited. Waiting {wait}s...')
                time.sleep(wait)
                return self._request(method, endpoint, json_data, data, files, headers)

            if not resp.ok:
                return {'error': True, 'status': resp.status_code, 'message': resp.text[:300]}

            return resp.json() if resp.text else {}
        except requests.RequestException as e:
            return {'error': True, 'message': str(e)}

    def upload_asset(self, file_path: Path) -> dict:
        """
        Upload a file to Webflow Assets.

        Returns: {'url': 'https://...', 'id': '...'} or {'error': ...}
        """
        file_name = file_path.name
        file_size = file_path.stat().st_size
        mime_type = mimetypes.guess_type(file_name)[0] or 'image/jpeg'

        # Step 1: Request upload URL
        upload_request = {
            'fileName': file_name,
            'fileHash': str(hash(file_name + str(file_size))),  # Simple hash
        }

        result = self._request(
            'POST',
            f'/sites/{self.site_id}/assets/upload',
            json_data=upload_request
        )

        if result.get('error'):
            return result

        upload_url = result.get('uploadUrl')
        upload_details = result.get('uploadDetails', {})
        asset_id = result.get('id')

        if not upload_url:
            return {'error': True, 'message': 'No upload URL returned'}

        # Step 2: Upload to S3
        self._rate_limit(0.1)  # Shorter delay for S3

        with open(file_path, 'rb') as f:
            file_data = f.read()

        # Build multipart form data for S3
        s3_fields = upload_details.copy()
        files = {
            'file': (file_name, file_data, mime_type)
        }

        try:
            s3_resp = requests.post(upload_url, data=s3_fields, files=files)
            if not s3_resp.ok:
                return {'error': True, 'message': f'S3 upload failed: {s3_resp.status_code}'}
        except Exception as e:
            return {'error': True, 'message': f'S3 upload error: {e}'}

        # Step 3: Get the asset URL
        # Wait a moment for processing
        time.sleep(1)

        asset_result = self._request('GET', f'/sites/{self.site_id}/assets/{asset_id}')
        if asset_result.get('error'):
            # Return what we have
            return {'id': asset_id, 'url': None, 'pending': True}

        return {
            'id': asset_id,
            'url': asset_result.get('url') or asset_result.get('hostedUrl'),
        }

    def get_all_ingredients(self):
        """Fetch all ingredients."""
        items = []
        offset = 0
        limit = 100

        while True:
            result = self._request('GET', f'/collections/{self.collection_id}/items?limit={limit}&offset={offset}')
            if result.get('error') or not result.get('items'):
                break

            items.extend(result['items'])
            if len(items) % 1000 == 0:
                print(f'  Fetched {len(items)} ingredients...')

            if len(result['items']) < limit:
                break
            offset += limit

        return items

    def build_indices(self, items):
        """Build matching indices."""
        exact_index = {}
        clean_index = {}
        all_items = []

        for item in items:
            name = item.get('fieldData', {}).get('name', '')
            if is_junk_name(name):
                continue

            if name:
                normalized = normalize_name(name)
                cleaned = clean_for_matching(name)

                exact_index[normalized] = item
                if cleaned and len(cleaned) > 3:
                    clean_index[cleaned] = item

                all_items.append({
                    'item': item,
                    'name': name,
                    'normalized': normalized,
                    'cleaned': cleaned,
                })

        return exact_index, clean_index, all_items

    def find_match(self, image_name, exact_index, clean_index, all_items):
        """Find best match for image."""
        normalized = normalize_name(image_name)
        cleaned = clean_for_matching(image_name)

        # Exact match
        if normalized in exact_index:
            return exact_index[normalized], 'exact', 1.0

        # Cleaned match
        if cleaned in clean_index:
            return clean_index[cleaned], 'cleaned', 0.95

        # Contains match (substantial strings only)
        for key, item in exact_index.items():
            if len(key) > 10 and (normalized in key or key in normalized):
                return item, 'contains', 0.85

        # Fuzzy match
        best_match = None
        best_score = 0

        for entry in all_items:
            score = max(
                similarity(normalized, entry['normalized']),
                similarity(cleaned, entry['cleaned'])
            )
            if score > best_score:
                best_score = score
                best_match = entry['item']

        if best_score >= 0.8:
            return best_match, 'fuzzy', best_score

        return None, None, 0

    def update_ingredient_image(self, item_id: str, image_url: str) -> bool:
        """Update ingredient's hero image."""
        result = self._request(
            'PATCH',
            f'/collections/{self.collection_id}/items/{item_id}',
            json_data={'fieldData': {'hero-image': image_url}}
        )
        return not result.get('error')

    def upload_and_link_images(self, images_folder: str, dry_run: bool = True, skip_existing: bool = True, limit: int = None):
        """
        Upload images to Webflow and link to ingredients.
        """
        images_path = Path(images_folder)
        if not images_path.exists():
            print(f'Error: Folder not found: {images_folder}')
            return

        # Get image files
        image_files = list(images_path.glob('*.jpg')) + list(images_path.glob('*.jpeg')) + \
                      list(images_path.glob('*.png')) + list(images_path.glob('*.webp'))

        print(f'Found {len(image_files)} images')

        # Fetch and index ingredients
        print('\nFetching ingredients from Webflow...')
        ingredients = self.get_all_ingredients()
        print(f'Total ingredients: {len(ingredients)}')

        print('Building match indices...')
        exact_index, clean_index, all_items = self.build_indices(ingredients)

        # Match images
        print('\nMatching images to ingredients...')
        to_upload = []
        skipped_existing = 0
        unmatched = []

        for img_path in image_files:
            item, match_type, confidence = self.find_match(img_path.name, exact_index, clean_index, all_items)

            if not item:
                unmatched.append(img_path.name)
                continue

            has_image = bool(item.get('fieldData', {}).get('hero-image'))

            if skip_existing and has_image:
                skipped_existing += 1
                continue

            to_upload.append({
                'image': img_path,
                'ingredient': item.get('fieldData', {}).get('name'),
                'item_id': item.get('id'),
                'match_type': match_type,
                'confidence': confidence,
            })

        print(f'\nTo upload: {len(to_upload)}')
        print(f'Skipped (already have image): {skipped_existing}')
        print(f'Unmatched: {len(unmatched)}')

        if limit:
            to_upload = to_upload[:limit]
            print(f'Limited to: {len(to_upload)}')

        if dry_run:
            print('\n[DRY RUN] Would upload:')
            for item in to_upload[:20]:
                print(f"  {item['image'].name} -> {item['ingredient']}")
            if len(to_upload) > 20:
                print(f'  ... and {len(to_upload) - 20} more')
            print('\nRun with --upload to actually upload.')
            return {'to_upload': len(to_upload), 'skipped': skipped_existing, 'unmatched': len(unmatched)}

        # Actually upload
        print('\n' + '='*50)
        print('UPLOADING IMAGES')
        print('='*50)

        uploaded = 0
        failed = 0

        for i, item in enumerate(to_upload):
            print(f"\n[{i+1}/{len(to_upload)}] {item['image'].name}")
            print(f"  -> {item['ingredient']}")

            # Upload to Webflow assets
            result = self.upload_asset(item['image'])

            if result.get('error'):
                print(f"  ✗ Upload failed: {result.get('message', 'Unknown error')}")
                failed += 1
                continue

            image_url = result.get('url')
            if not image_url:
                print(f"  ✗ No URL returned (asset may still be processing)")
                failed += 1
                continue

            print(f"  ✓ Uploaded: {image_url[:60]}...")

            # Link to ingredient
            if self.update_ingredient_image(item['item_id'], image_url):
                print(f"  ✓ Linked to ingredient")
                uploaded += 1
            else:
                print(f"  ✗ Failed to link")
                failed += 1

        print('\n' + '='*50)
        print('UPLOAD COMPLETE')
        print('='*50)
        print(f'Uploaded and linked: {uploaded}')
        print(f'Failed: {failed}')
        print(f'Skipped (existing): {skipped_existing}')

        return {'uploaded': uploaded, 'failed': failed, 'skipped': skipped_existing}


if __name__ == '__main__':
    images_folder = os.path.expanduser('~/Downloads/ingredient_images_1000x1000')
    dry_run = '--upload' not in sys.argv
    limit = None

    # Parse limit argument
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    print('='*50)
    print('WEBFLOW ASSET UPLOADER')
    print('='*50)
    print()

    uploader = WebflowAssetUploader()
    result = uploader.upload_and_link_images(images_folder, dry_run=dry_run, limit=limit)

    if dry_run:
        print('\nTo upload images, run:')
        print('  python3 webflow_asset_upload.py --upload')
        print('  python3 webflow_asset_upload.py --upload --limit=10  # Test with 10 first')
