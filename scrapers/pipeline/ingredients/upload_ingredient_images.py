"""
Upload ingredient images to Webflow CMS.

Matches images from ingredient_images_1000x1000 folder to ingredients
by name and uploads them as hero images.
"""

import os
import sys
import time
import re
from pathlib import Path

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
    # Remove file extension
    name = re.sub(r'\.(jpg|jpeg|png|gif|webp)$', '', name, flags=re.IGNORECASE)
    # Normalize whitespace and case
    name = name.strip().lower()
    # Replace underscores with spaces
    name = name.replace('_', ' ')
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name)
    return name


class WebflowImageUploader:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.site_id = os.environ.get('WEBFLOW_SITE_ID', '')
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

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_request = time.time()

    def _request(self, method: str, endpoint: str, data=None, files=None, json_data=None):
        self._rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'

        try:
            headers = dict(self.session.headers)
            if json_data:
                headers['Content-Type'] = 'application/json'
                resp = self.session.request(method, url, json=json_data, headers=headers)
            elif files:
                # Remove Content-Type for multipart
                headers.pop('Content-Type', None)
                resp = self.session.request(method, url, data=data, files=files, headers=headers)
            else:
                resp = self.session.request(method, url, json=data, headers=headers)

            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 60))
                print(f'Rate limited. Waiting {wait}s...')
                time.sleep(wait)
                return self._request(method, endpoint, data, files, json_data)

            if not resp.ok:
                print(f'API Error {resp.status_code}: {resp.text[:300]}')
                return None

            return resp.json() if resp.text else {}

        except requests.RequestException as e:
            print(f'Request error: {e}')
            return None

    def get_all_ingredients(self):
        """Fetch all ingredients from Webflow."""
        items = []
        offset = 0
        limit = 100

        while True:
            result = self._request('GET', f'/collections/{self.collection_id}/items?limit={limit}&offset={offset}')
            if not result or not result.get('items'):
                break

            items.extend(result['items'])
            print(f'  Fetched {len(items)} ingredients...')

            if len(result['items']) < limit:
                break
            offset += limit

        return items

    def build_name_index(self, items):
        """Build index of ingredients by normalized name."""
        index = {}
        for item in items:
            name = item.get('fieldData', {}).get('name', '')
            if name:
                normalized = normalize_name(name)
                index[normalized] = item
        return index

    def update_item_image(self, item_id: str, image_url: str) -> bool:
        """Update an ingredient's hero image."""
        data = {
            'fieldData': {
                'hero-image': {'url': image_url}
            }
        }
        result = self._request('PATCH', f'/collections/{self.collection_id}/items/{item_id}', json_data=data)
        return result is not None

    def upload_to_webflow_assets(self, file_path: str, file_name: str) -> str:
        """
        Upload image to Webflow Assets and return the URL.

        Note: Webflow v2 API asset upload requires:
        1. Create asset folder (optional)
        2. Get presigned upload URL
        3. Upload file to S3
        4. Confirm upload
        """
        # For now, we'll use an external image host or the direct URL approach
        # Webflow accepts image URLs directly in item updates

        # Since we can't easily upload to Webflow assets without complex S3 flow,
        # we'll need to host images elsewhere first (like Cloudinary, S3, or Google Drive)
        # Then use those URLs

        return None

    def upload_images(self, images_folder: str, dry_run: bool = True):
        """
        Upload images to Webflow ingredients.

        Args:
            images_folder: Path to folder containing ingredient images
            dry_run: If True, only show matches without uploading
        """
        images_path = Path(images_folder)
        if not images_path.exists():
            print(f'Error: Folder not found: {images_folder}')
            return

        # Get all image files
        image_files = list(images_path.glob('*.jpg')) + list(images_path.glob('*.jpeg')) + \
                      list(images_path.glob('*.png')) + list(images_path.glob('*.webp'))

        print(f'Found {len(image_files)} images in {images_folder}')

        # Fetch ingredients
        print('\nFetching ingredients from Webflow...')
        ingredients = self.get_all_ingredients()
        print(f'Total ingredients: {len(ingredients)}')

        # Build name index
        name_index = self.build_name_index(ingredients)
        print(f'Built name index with {len(name_index)} entries')

        # Match images to ingredients
        print('\nMatching images to ingredients...')
        matched = []
        unmatched = []

        for img_path in image_files:
            img_name = normalize_name(img_path.name)

            if img_name in name_index:
                item = name_index[img_name]
                matched.append({
                    'image': img_path,
                    'ingredient': item.get('fieldData', {}).get('name'),
                    'item_id': item.get('id'),
                    'has_image': bool(item.get('fieldData', {}).get('hero-image'))
                })
            else:
                unmatched.append(img_path.name)

        print(f'\nMatched: {len(matched)}')
        print(f'Unmatched: {len(unmatched)}')

        # Show matches
        if matched:
            print('\n--- MATCHED IMAGES ---')
            for m in matched[:20]:
                status = '(has image)' if m['has_image'] else '(no image)'
                print(f"  {m['image'].name} -> {m['ingredient']} {status}")
            if len(matched) > 20:
                print(f'  ... and {len(matched) - 20} more')

        # Show some unmatched
        if unmatched:
            print('\n--- UNMATCHED IMAGES (first 20) ---')
            for name in unmatched[:20]:
                print(f'  {name}')
            if len(unmatched) > 20:
                print(f'  ... and {len(unmatched) - 20} more')

        if dry_run:
            print('\n[DRY RUN] No images uploaded.')
            print('\nNote: To upload images to Webflow, they need to be hosted first.')
            print('Options:')
            print('  1. Upload to Google Drive and use public URLs')
            print('  2. Upload to Cloudinary or similar CDN')
            print('  3. Use Webflow asset upload (complex S3 flow)')
            return {'matched': len(matched), 'unmatched': len(unmatched)}

        # TODO: Implement actual upload when image hosting is set up
        return {'matched': len(matched), 'unmatched': len(unmatched)}


if __name__ == '__main__':
    import sys

    # Default images folder
    images_folder = os.path.expanduser('~/Downloads/ingredient_images_1000x1000')

    if len(sys.argv) > 1:
        images_folder = sys.argv[1]

    print('=' * 50)
    print('WEBFLOW INGREDIENT IMAGE UPLOADER')
    print('=' * 50)
    print()

    uploader = WebflowImageUploader()
    result = uploader.upload_images(images_folder, dry_run=True)
