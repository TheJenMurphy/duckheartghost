"""
Set placeholder hero image for all ingredients that don't have one.

Usage:
    python set_placeholder_images.py <PLACEHOLDER_IMAGE_URL>

Example:
    python set_placeholder_images.py "https://cdn.prod.website-files.com/6759f0a54f1395fcb6c5b78e/YOUR_IMAGE_ID_9s-question-mark.png"

This will update all ingredients in Webflow that have no hero-image to use
the provided placeholder URL.
"""

import os
import sys
import time
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


class PlaceholderImageSetter:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.collection_id = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')

        if not self.api_token:
            raise ValueError("WEBFLOW_API_TOKEN not set in environment")
        if not self.collection_id:
            raise ValueError("WEBFLOW_INGREDIENTS_COLLECTION_ID not set in environment")

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
        })
        self._last_request = 0

    def _rate_limit(self):
        """Respect Webflow rate limits (60 req/min)."""
        elapsed = time.time() - self._last_request
        if elapsed < 1.0:  # 1 second between requests to be safe
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

    def get_ingredients_without_hero_image(self, items):
        """Filter ingredients that have no hero image."""
        missing = []
        for item in items:
            field_data = item.get('fieldData', {})
            hero_image = field_data.get('hero-image')

            # Check if hero-image is missing or empty
            if not hero_image or (isinstance(hero_image, dict) and not hero_image.get('url')):
                missing.append({
                    'id': item.get('id'),
                    'name': field_data.get('name', 'Unknown'),
                    'slug': field_data.get('slug', '')
                })

        return missing

    def update_hero_image(self, item_id: str, image_url: str) -> bool:
        """Update an ingredient's hero image."""
        data = {
            'fieldData': {
                'hero-image': {'url': image_url}
            }
        }
        result = self._request('PATCH', f'/collections/{self.collection_id}/items/{item_id}', json_data=data)
        return result is not None

    def set_placeholders(self, placeholder_url: str, dry_run: bool = True):
        """
        Set placeholder image for all ingredients without a hero image.

        Args:
            placeholder_url: URL of the placeholder image (must be hosted)
            dry_run: If True, only show what would be updated without making changes
        """
        print('=' * 60)
        print('SET PLACEHOLDER HERO IMAGES')
        print('=' * 60)
        print(f'\nPlaceholder URL: {placeholder_url}')
        print(f'Mode: {"DRY RUN" if dry_run else "LIVE UPDATE"}\n')

        # Fetch all ingredients
        print('Fetching ingredients from Webflow...')
        ingredients = self.get_all_ingredients()
        print(f'Total ingredients: {len(ingredients)}\n')

        # Find those without hero images
        missing = self.get_ingredients_without_hero_image(ingredients)
        print(f'Ingredients WITHOUT hero image: {len(missing)}\n')

        if not missing:
            print('All ingredients already have hero images!')
            return {'total': len(ingredients), 'updated': 0}

        # Show what will be updated
        print('Ingredients to update:')
        for i, item in enumerate(missing[:20]):
            print(f"  {i+1}. {item['name']}")
        if len(missing) > 20:
            print(f'  ... and {len(missing) - 20} more\n')

        if dry_run:
            print('\n[DRY RUN] No changes made.')
            print(f'\nTo apply changes, run with --live flag:')
            print(f'  python set_placeholder_images.py "{placeholder_url}" --live')
            return {'total': len(ingredients), 'would_update': len(missing)}

        # Actually update
        print(f'\nUpdating {len(missing)} ingredients...')
        updated = 0
        failed = 0

        for i, item in enumerate(missing):
            success = self.update_hero_image(item['id'], placeholder_url)
            if success:
                updated += 1
                print(f"  [{i+1}/{len(missing)}] Updated: {item['name']}")
            else:
                failed += 1
                print(f"  [{i+1}/{len(missing)}] FAILED: {item['name']}")

        print(f'\n{"=" * 60}')
        print(f'COMPLETE: Updated {updated} ingredients, {failed} failed')
        print('=' * 60)

        return {'total': len(ingredients), 'updated': updated, 'failed': failed}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print('\nError: Please provide the placeholder image URL as an argument.')
        print('\nSteps:')
        print('  1. Upload 9s-question-mark.png to Webflow Assets (via dashboard)')
        print('  2. Copy the CDN URL')
        print('  3. Run: python set_placeholder_images.py "YOUR_CDN_URL"')
        sys.exit(1)

    placeholder_url = sys.argv[1]

    # Check for --live flag
    dry_run = '--live' not in sys.argv

    # Validate URL
    if not placeholder_url.startswith('http'):
        print(f'Error: Invalid URL: {placeholder_url}')
        print('URL must start with http:// or https://')
        sys.exit(1)

    setter = PlaceholderImageSetter()
    setter.set_placeholders(placeholder_url, dry_run=dry_run)


if __name__ == '__main__':
    main()
