"""
Fuzzy match ingredient images to Webflow ingredients.

Uses multiple matching strategies:
1. Exact match (normalized)
2. Contains match
3. Fuzzy string matching
"""

import os
import sys
import time
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


def normalize_name(name):
    """Normalize ingredient name for matching."""
    name = re.sub(r'\.(jpg|jpeg|png|gif|webp)$', '', name, flags=re.IGNORECASE)
    name = name.strip().lower()
    name = name.replace('_', ' ')
    name = re.sub(r'\s+', ' ', name)
    return name


# Junk ingredient names to skip during matching
JUNK_NAMES = {
    'ext', 'pharmaceutical secondary standard', '●  oils', '● oils',
    '1', '2', '3', '3s', '4aa', 'pharmagrade', 'powder', 'mixture of isomers',
    'puriss', 'beantree', '959610-30-1', '●  titanium(iv) oxide',
}


def is_junk_name(name):
    """Check if a name is a junk/invalid ingredient name."""
    normalized = normalize_name(name)
    if normalized in JUNK_NAMES:
        return True
    # Also skip very short names or names that are just numbers/codes
    if len(normalized) <= 3:
        return True
    if re.match(r'^[\d\-]+$', normalized):
        return True
    if normalized.startswith('●'):
        return True
    return False


def clean_for_matching(name):
    """Clean name for fuzzy matching - remove parentheses, special chars."""
    name = normalize_name(name)
    # Remove parenthetical content
    name = re.sub(r'\([^)]*\)', '', name)
    # Remove special characters
    name = re.sub(r'[^a-z0-9\s]', '', name)
    # Normalize whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def similarity(a, b):
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()


class WebflowImageMatcher:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.collection_id = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')

        if not self.api_token:
            raise ValueError("WEBFLOW_API_TOKEN not set")

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

    def _request(self, method: str, endpoint: str, data=None, json_data=None):
        self._rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'

        try:
            if json_data:
                resp = self.session.request(method, url, json=json_data)
            else:
                resp = self.session.request(method, url, json=data)

            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 60))
                print(f'Rate limited. Waiting {wait}s...')
                time.sleep(wait)
                return self._request(method, endpoint, data, json_data)

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
            if len(items) % 500 == 0:
                print(f'  Fetched {len(items)} ingredients...')

            if len(result['items']) < limit:
                break
            offset += limit

        return items

    def build_indices(self, items):
        """Build multiple indices for matching."""
        exact_index = {}  # normalized name -> item
        clean_index = {}  # cleaned name -> item
        all_items = []    # for fuzzy matching

        for item in items:
            name = item.get('fieldData', {}).get('name', '')
            inci = item.get('fieldData', {}).get('inci', '')

            # Skip junk entries
            if is_junk_name(name):
                continue

            if name:
                normalized = normalize_name(name)
                cleaned = clean_for_matching(name)

                exact_index[normalized] = item
                if cleaned and len(cleaned) > 3:  # Skip very short cleaned names
                    clean_index[cleaned] = item

                all_items.append({
                    'item': item,
                    'name': name,
                    'normalized': normalized,
                    'cleaned': cleaned,
                })

            # Also index by INCI if different
            if inci:
                # Strip HTML tags from INCI
                inci_clean = re.sub(r'<[^>]+>', '', inci)
                inci_normalized = normalize_name(inci_clean)
                if inci_normalized and inci_normalized not in exact_index and not is_junk_name(inci_clean):
                    exact_index[inci_normalized] = item

        return exact_index, clean_index, all_items

    def find_match(self, image_name, exact_index, clean_index, all_items):
        """
        Find best match for an image name using multiple strategies.

        Returns: (matched_item, match_type, confidence)
        """
        normalized = normalize_name(image_name)
        cleaned = clean_for_matching(image_name)

        # Strategy 1: Exact match on normalized name
        if normalized in exact_index:
            return exact_index[normalized], 'exact', 1.0

        # Strategy 2: Exact match on cleaned name
        if cleaned in clean_index:
            return clean_index[cleaned], 'cleaned', 0.95

        # Strategy 3: Check if image name contains ingredient name or vice versa
        # Only match if the contained string is substantial (>10 chars)
        for key, item in exact_index.items():
            if len(key) > 10 and (normalized in key or key in normalized):
                return item, 'contains', 0.85

        # Strategy 4: Fuzzy match (expensive, only for remaining)
        best_match = None
        best_score = 0
        best_type = None

        for entry in all_items:
            # Try normalized
            score = similarity(normalized, entry['normalized'])
            if score > best_score:
                best_score = score
                best_match = entry['item']
                best_type = 'fuzzy-normalized'

            # Try cleaned
            score = similarity(cleaned, entry['cleaned'])
            if score > best_score:
                best_score = score
                best_match = entry['item']
                best_type = 'fuzzy-cleaned'

        if best_score >= 0.8:
            return best_match, best_type, best_score

        return None, None, 0

    def update_item_image(self, item_id: str, image_url: str) -> bool:
        """Update an ingredient's hero image."""
        data = {
            'fieldData': {
                'hero-image': {'url': image_url}
            }
        }
        result = self._request('PATCH', f'/collections/{self.collection_id}/items/{item_id}', json_data=data)
        return result is not None

    def match_images(self, images_folder: str, dry_run: bool = True, update_webflow: bool = False, gdrive_base_url: str = None):
        """
        Match images to ingredients with fuzzy matching.
        """
        images_path = Path(images_folder)
        if not images_path.exists():
            print(f'Error: Folder not found: {images_folder}')
            return

        # Get all image files
        image_files = list(images_path.glob('*.jpg')) + list(images_path.glob('*.jpeg')) + \
                      list(images_path.glob('*.png')) + list(images_path.glob('*.webp'))

        print(f'Found {len(image_files)} images')

        # Fetch and index ingredients
        print('\nFetching ingredients from Webflow...')
        ingredients = self.get_all_ingredients()
        print(f'Total ingredients: {len(ingredients)}')

        print('\nBuilding match indices...')
        exact_index, clean_index, all_items = self.build_indices(ingredients)

        # Match images
        print('\nMatching images to ingredients...')
        matched = []
        unmatched = []
        match_stats = {'exact': 0, 'cleaned': 0, 'contains': 0, 'fuzzy-normalized': 0, 'fuzzy-cleaned': 0}

        for i, img_path in enumerate(image_files):
            item, match_type, confidence = self.find_match(img_path.name, exact_index, clean_index, all_items)

            if item:
                matched.append({
                    'image': img_path,
                    'ingredient': item.get('fieldData', {}).get('name'),
                    'item_id': item.get('id'),
                    'match_type': match_type,
                    'confidence': confidence,
                    'has_image': bool(item.get('fieldData', {}).get('hero-image'))
                })
                match_stats[match_type] = match_stats.get(match_type, 0) + 1
            else:
                unmatched.append(img_path.name)

            if (i + 1) % 50 == 0:
                print(f'  Processed {i + 1}/{len(image_files)} images...')

        print(f'\n{"="*50}')
        print('MATCH RESULTS')
        print('='*50)
        print(f'Matched: {len(matched)}')
        print(f'Unmatched: {len(unmatched)}')
        print(f'\nMatch types:')
        for mt, count in match_stats.items():
            if count > 0:
                print(f'  {mt}: {count}')

        # Show some matches
        print(f'\n--- SAMPLE MATCHES ---')
        for m in matched[:15]:
            conf = f"{m['confidence']:.0%}" if m['confidence'] < 1 else "100%"
            has_img = '✓' if m['has_image'] else '○'
            print(f"  [{has_img}] {m['image'].name[:50]}")
            print(f"      -> {m['ingredient'][:50]} ({m['match_type']}, {conf})")

        # Show unmatched
        if unmatched:
            print(f'\n--- UNMATCHED ({len(unmatched)}) ---')
            for name in unmatched[:10]:
                print(f'  {name}')
            if len(unmatched) > 10:
                print(f'  ... and {len(unmatched) - 10} more')

        # Update Webflow if requested
        if update_webflow and gdrive_base_url and not dry_run:
            print(f'\n--- UPDATING WEBFLOW ---')
            updated = 0
            skipped = 0

            for m in matched:
                if m['has_image']:
                    skipped += 1
                    continue

                # Construct Google Drive URL
                image_url = f"{gdrive_base_url}/{m['image'].name}"

                if self.update_item_image(m['item_id'], image_url):
                    updated += 1
                    print(f"  Updated: {m['ingredient']}")
                else:
                    print(f"  Failed: {m['ingredient']}")

            print(f'\nUpdated: {updated}')
            print(f'Skipped (already has image): {skipped}')

        return {
            'matched': len(matched),
            'unmatched': len(unmatched),
            'match_details': matched,
            'unmatched_list': unmatched
        }


if __name__ == '__main__':
    images_folder = os.path.expanduser('~/Downloads/ingredient_images_1000x1000')

    print('=' * 50)
    print('FUZZY IMAGE MATCHER')
    print('=' * 50)
    print()

    matcher = WebflowImageMatcher()
    result = matcher.match_images(images_folder, dry_run=True)

    # Save unmatched to file for review
    if result['unmatched_list']:
        with open('/tmp/unmatched_images.txt', 'w') as f:
            for name in result['unmatched_list']:
                f.write(f"{name}\n")
        print(f"\nUnmatched images saved to /tmp/unmatched_images.txt")
