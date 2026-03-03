"""
Cleanup duplicate/junk ingredients from Webflow CMS.

Identifies and removes obvious junk entries like:
- EXT, PHARMACEUTICAL SECONDARY STANDARD, ● OILS
- Numbers: 1, 2, 3, 3S
- PHARMAGRADE, POWDER, MIXTURE OF ISOMERS, PURISS
"""

import os
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

# Junk ingredient names to delete
JUNK_NAMES = {
    'EXT',
    'PHARMACEUTICAL SECONDARY STANDARD',
    '●  OILS',
    '● OILS',
    '1',
    '2',
    '3',
    '3S',
    'PHARMAGRADE',
    'POWDER',
    'MIXTURE OF ISOMERS',
    'PURISS',
}


class WebflowCleanup:
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
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        self._last_request = 0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_request = time.time()

    def _request(self, method: str, endpoint: str, data=None):
        self._rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'

        try:
            if method == 'GET':
                resp = self.session.get(url)
            elif method == 'DELETE':
                resp = self.session.delete(url)
            elif method == 'POST':
                resp = self.session.post(url, json=data)
            else:
                raise ValueError(f'Unknown method: {method}')

            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 60))
                print(f'Rate limited. Waiting {wait}s...')
                time.sleep(wait)
                return self._request(method, endpoint, data)

            if not resp.ok:
                print(f'API Error {resp.status_code}: {resp.text[:200]}')
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

    def find_junk_items(self, items):
        """Find items that match junk names."""
        junk = []
        for item in items:
            name = item.get('fieldData', {}).get('name', '')
            if name in JUNK_NAMES:
                junk.append({
                    'id': item['id'],
                    'name': name,
                })
        return junk

    def delete_item(self, item_id: str) -> bool:
        """Delete a single item."""
        result = self._request('DELETE', f'/collections/{self.collection_id}/items/{item_id}')
        return result is not None

    def cleanup(self, dry_run=True):
        """
        Find and delete junk ingredients.

        Args:
            dry_run: If True, only show what would be deleted
        """
        print('Fetching all ingredients from Webflow...')
        items = self.get_all_ingredients()
        print(f'Total ingredients: {len(items)}')

        print('\nFinding junk items...')
        junk = self.find_junk_items(items)
        print(f'Found {len(junk)} junk items to delete:')

        # Group by name for display
        by_name = {}
        for item in junk:
            name = item['name']
            if name not in by_name:
                by_name[name] = []
            by_name[name].append(item['id'])

        for name, ids in sorted(by_name.items(), key=lambda x: -len(x[1])):
            print(f'  {len(ids)}x: {name}')

        if dry_run:
            print('\n[DRY RUN] No items deleted. Run with --delete to actually delete.')
            return {'found': len(junk), 'deleted': 0}

        print('\nDeleting junk items...')
        deleted = 0
        for i, item in enumerate(junk):
            print(f'  [{i+1}/{len(junk)}] Deleting: {item["name"]} ({item["id"][:8]}...)')
            if self.delete_item(item['id']):
                deleted += 1
            else:
                print(f'    Failed to delete!')

        print(f'\nDeleted {deleted}/{len(junk)} items')
        return {'found': len(junk), 'deleted': deleted}


if __name__ == '__main__':
    import sys

    dry_run = '--delete' not in sys.argv

    print('=' * 50)
    print('WEBFLOW INGREDIENT CLEANUP')
    print('=' * 50)
    print()

    cleanup = WebflowCleanup()
    result = cleanup.cleanup(dry_run=dry_run)

    print()
    print('=' * 50)
    print('SUMMARY')
    print('=' * 50)
    print(f'Junk items found: {result["found"]}')
    print(f'Items deleted: {result["deleted"]}')

    if dry_run and result['found'] > 0:
        print()
        print('To actually delete these items, run:')
        print('  python cleanup_duplicates.py --delete')
