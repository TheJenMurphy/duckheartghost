"""
Smart ingredient image uploader.

Uses the organized folder with multiple images per ingredient.
Picks best images for each of Webflow's 3 gallery slots based on naming patterns:
- hero-image: "on white", studio shots
- in-the-field-image: "branch", "field", "plant" shots
- gallery-image-3: additional image
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


JUNK_NAMES = {'ext', 'pharmaceutical secondary standard', '1', '2', '3', '3s', 'powder', 'puriss'}


def is_junk_name(name):
    normalized = normalize_name(name)
    if normalized in JUNK_NAMES:
        return True
    if len(normalized) <= 3:
        return True
    if normalized.startswith('●'):
        return True
    return False


def classify_image(filename):
    """
    Classify image type based on filename.
    Returns: 'hero', 'field', 'other'

    Hero priority: white background, transparent, isolated, studio shots
    """
    lower = filename.lower()

    # Hero indicators (white/transparent background, studio shots) - HIGHEST priority
    hero_patterns = [
        'on white', 'white background', 'transparent', 'isolated',
        'studio', 'product shot', 'cutout', 'png',  # PNG often = transparent
        'clean background', 'white bg', 'pure white'
    ]
    for pattern in hero_patterns:
        if pattern in lower:
            return 'hero'

    # Secondary hero indicators (close-ups, detail shots)
    hero_secondary = ['closeup', 'close-up', 'close up', 'macro', 'detail', 'tight']
    for pattern in hero_secondary:
        if pattern in lower:
            return 'hero'

    # Field/botanical indicators (in nature shots)
    field_patterns = [
        'branch', 'field', 'plant', 'growing', 'nature', 'garden',
        'wild', 'farm', 'tree', 'bush', 'flower', 'outdoor',
        'harvest', 'botanical', 'leaf', 'stem', 'root'
    ]
    for pattern in field_patterns:
        if pattern in lower:
            return 'field'

    # If "also" or alternate indicators
    if 'also' in lower or 'alt' in lower or 'variant' in lower:
        return 'other'

    # Check file extension - PNG often has transparent bg
    if lower.endswith('.png'):
        return 'hero'

    return 'other'


def pick_best_images(image_files, max_images=6):
    """
    Pick best images for each slot from a list of image files.
    Returns: {'hero': path, 'field': path, 'gallery3': path, 'gallery4': path, 'gallery5': path, 'gallery6': path}
    """
    classified = {'hero': [], 'field': [], 'other': []}

    for img_path in image_files:
        img_type = classify_image(img_path.name)
        classified[img_type].append(img_path)

    result = {}
    used = set()

    # Pick hero (prefer classified hero, else first image)
    if classified['hero']:
        result['hero'] = classified['hero'][0]
        used.add(classified['hero'][0])
    elif classified['other']:
        result['hero'] = classified['other'][0]
        used.add(classified['other'][0])
    elif classified['field']:
        result['hero'] = classified['field'][0]
        used.add(classified['field'][0])

    # Pick field image
    for img in classified['field']:
        if img not in used:
            result['field'] = img
            used.add(img)
            break
    if 'field' not in result:
        for img in classified['other']:
            if img not in used:
                result['field'] = img
                used.add(img)
                break

    # Pick remaining images for gallery slots 3-6
    remaining = []
    for img_type in ['hero', 'other', 'field']:  # Prioritize hero-type, then other, then field
        for img in classified[img_type]:
            if img not in used:
                remaining.append(img)

    gallery_slots = ['gallery3', 'gallery4', 'gallery5', 'gallery6']
    for i, slot in enumerate(gallery_slots):
        if i < len(remaining):
            result[slot] = remaining[i]

    return result


class SmartImageUploader:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.site_id = os.environ.get('WEBFLOW_SITE_ID', '')
        self.collection_id = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')

        if not self.api_token:
            raise ValueError("WEBFLOW_API_TOKEN not set")
        if not self.site_id:
            raise ValueError("WEBFLOW_SITE_ID not set")

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

    def _request(self, method, endpoint, json_data=None, data=None, files=None):
        self._rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'

        try:
            if files:
                headers = dict(self.session.headers)
                headers.pop('Content-Type', None)
                resp = requests.request(method, url, data=data, files=files, headers=headers)
            elif json_data:
                resp = self.session.request(method, url, json=json_data)
            else:
                resp = self.session.request(method, url)

            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 60))
                print(f'Rate limited. Waiting {wait}s...')
                time.sleep(wait)
                return self._request(method, endpoint, json_data, data, files)

            if not resp.ok:
                return {'error': True, 'status': resp.status_code, 'message': resp.text[:200]}

            return resp.json() if resp.text else {}
        except Exception as e:
            return {'error': True, 'message': str(e)}

    def upload_asset(self, file_path):
        """Upload file to Webflow Assets."""
        file_name = file_path.name
        file_size = file_path.stat().st_size

        # Request upload URL
        result = self._request('POST', f'/sites/{self.site_id}/assets/upload',
                              json_data={'fileName': file_name, 'fileHash': f'{hash(file_name)}{file_size}'})

        if result.get('error'):
            return result

        upload_url = result.get('uploadUrl')
        upload_details = result.get('uploadDetails', {})
        asset_id = result.get('id')

        if not upload_url:
            return {'error': True, 'message': 'No upload URL'}

        # Upload to S3
        with open(file_path, 'rb') as f:
            file_data = f.read()

        try:
            s3_resp = requests.post(upload_url, data=upload_details,
                                   files={'file': (file_name, file_data, 'image/jpeg')})
            if not s3_resp.ok:
                return {'error': True, 'message': f'S3 failed: {s3_resp.status_code}'}
        except Exception as e:
            return {'error': True, 'message': str(e)}

        # Get asset URL
        time.sleep(1)
        asset = self._request('GET', f'/sites/{self.site_id}/assets/{asset_id}')

        return {
            'id': asset_id,
            'url': asset.get('url') or asset.get('hostedUrl') if not asset.get('error') else None
        }

    def get_all_ingredients(self):
        """Fetch all ingredients."""
        items = []
        offset = 0

        while True:
            result = self._request('GET', f'/collections/{self.collection_id}/items?limit=100&offset={offset}')
            if result.get('error') or not result.get('items'):
                break
            items.extend(result['items'])
            if len(items) % 1000 == 0:
                print(f'  Fetched {len(items)}...')
            if len(result['items']) < 100:
                break
            offset += 100

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
                all_items.append({'item': item, 'normalized': normalized, 'cleaned': cleaned})

        return exact_index, clean_index, all_items

    def find_match(self, folder_name, exact_index, clean_index, all_items):
        """Find matching ingredient."""
        normalized = normalize_name(folder_name)
        cleaned = clean_for_matching(folder_name)

        if normalized in exact_index:
            return exact_index[normalized], 'exact'
        if cleaned in clean_index:
            return clean_index[cleaned], 'cleaned'

        # Fuzzy match
        best_match, best_score = None, 0
        for entry in all_items:
            score = max(similarity(normalized, entry['normalized']),
                       similarity(cleaned, entry['cleaned']))
            if score > best_score:
                best_score = score
                best_match = entry['item']

        if best_score >= 0.85:
            return best_match, f'fuzzy-{best_score:.0%}'

        return None, None

    def find_all_matches(self, folder_name, exact_index, clean_index, all_items):
        """
        Find ALL matching ingredients for an image folder.

        For botanical ingredients like "Rosa Damascena", this will match:
        - Rosa Damascena Extract
        - Rosa Damascena Flower Water
        - Rosa Damascena Wax
        - etc.
        """
        normalized = normalize_name(folder_name)
        cleaned = clean_for_matching(folder_name)
        matches = []

        # Exact match
        if normalized in exact_index:
            matches.append((exact_index[normalized], 'exact'))

        # Check if folder name is contained in ingredient names (botanical matching)
        # Only for substantial names (>8 chars to avoid false positives)
        if len(cleaned) >= 8:
            for entry in all_items:
                # Skip if already matched
                if any(m[0].get('id') == entry['item'].get('id') for m in matches):
                    continue

                # Check if folder name is contained in ingredient name
                if cleaned in entry['cleaned'] or entry['cleaned'] in cleaned:
                    matches.append((entry['item'], 'botanical'))

        # Fuzzy match for remaining (if no matches yet)
        if not matches:
            best_match, best_score = None, 0
            for entry in all_items:
                score = max(similarity(normalized, entry['normalized']),
                           similarity(cleaned, entry['cleaned']))
                if score > best_score:
                    best_score = score
                    best_match = entry['item']

            if best_score >= 0.85:
                matches.append((best_match, f'fuzzy-{best_score:.0%}'))

        return matches

    def update_ingredient_images(self, item_id, hero_url=None, field_url=None,
                                   gallery3_url=None, gallery4_url=None,
                                   gallery5_url=None, gallery6_url=None):
        """Update ingredient's images (all 6 gallery slots)."""
        field_data = {}
        if hero_url:
            field_data['hero-image'] = hero_url
        if field_url:
            field_data['in-the-field-image'] = field_url
        if gallery3_url:
            field_data['gallery-image-3'] = gallery3_url
        if gallery4_url:
            field_data['gallery-image-4'] = gallery4_url
        if gallery5_url:
            field_data['gallery-image-5'] = gallery5_url
        if gallery6_url:
            field_data['gallery-image-6'] = gallery6_url

        if not field_data:
            return True

        result = self._request('PATCH', f'/collections/{self.collection_id}/items/{item_id}',
                              json_data={'fieldData': field_data})
        return not result.get('error')

    def process_organized_folder(self, base_folder, dry_run=True, limit=None):
        """Process organized folder with subfolders per ingredient."""
        base_path = Path(base_folder)

        if not base_path.exists():
            print(f'Error: Folder not found: {base_folder}')
            return

        # Get ingredient folders
        folders = [f for f in base_path.iterdir() if f.is_dir() and not f.name.startswith('.')]
        print(f'Found {len(folders)} ingredient folders')

        # Fetch and index ingredients
        print('\nFetching ingredients from Webflow...')
        ingredients = self.get_all_ingredients()
        print(f'Total ingredients: {len(ingredients)}')

        exact_index, clean_index, all_items = self.build_indices(ingredients)

        # Process folders
        print('\nProcessing folders...')
        to_upload = []
        unmatched = []
        botanical_matches = 0

        for folder in folders:
            if folder.name == 'References':
                continue

            # Get images in folder
            images = list(folder.glob('*.jpg')) + list(folder.glob('*.jpeg')) + list(folder.glob('*.png'))

            if not images:
                continue

            # Find ALL matching ingredients (botanical matching)
            matches = self.find_all_matches(folder.name, exact_index, clean_index, all_items)

            if not matches:
                unmatched.append(folder.name)
                continue

            if len(matches) > 1:
                botanical_matches += len(matches) - 1

            # Pick best images
            best = pick_best_images(images)

            # Create upload info for each matched ingredient
            for item, match_type in matches:
                field_data = item.get('fieldData', {})
                has_hero = bool(field_data.get('hero-image'))
                has_field = bool(field_data.get('in-the-field-image'))
                has_gallery3 = bool(field_data.get('gallery-image-3'))
                has_gallery4 = bool(field_data.get('gallery-image-4'))
                has_gallery5 = bool(field_data.get('gallery-image-5'))
                has_gallery6 = bool(field_data.get('gallery-image-6'))

                upload_info = {
                    'folder': folder.name,
                    'ingredient': field_data.get('name'),
                    'item_id': item.get('id'),
                    'match_type': match_type,
                    'hero': best.get('hero') if not has_hero else None,
                    'field': best.get('field') if not has_field else None,
                    'gallery3': best.get('gallery3') if not has_gallery3 else None,
                    'gallery4': best.get('gallery4') if not has_gallery4 else None,
                    'gallery5': best.get('gallery5') if not has_gallery5 else None,
                    'gallery6': best.get('gallery6') if not has_gallery6 else None,
                }

                # Check if any images to upload
                has_uploads = any([upload_info['hero'], upload_info['field'],
                                  upload_info['gallery3'], upload_info['gallery4'],
                                  upload_info['gallery5'], upload_info['gallery6']])

                if has_uploads:
                    to_upload.append(upload_info)

        print(f'Botanical matches (variants): {botanical_matches}')

        print(f'\nTo upload: {len(to_upload)} ingredients with new images')
        print(f'Unmatched folders: {len(unmatched)}')

        if limit:
            to_upload = to_upload[:limit]

        if dry_run:
            print('\n[DRY RUN] Would upload:')
            for item in to_upload[:15]:
                parts = []
                if item.get('hero'):
                    parts.append(f"hero")
                if item.get('field'):
                    parts.append(f"field")
                for slot in ['gallery3', 'gallery4', 'gallery5', 'gallery6']:
                    if item.get(slot):
                        parts.append(slot.replace('gallery', 'g'))
                img_count = len(parts)
                print(f"  {item['ingredient'][:45]}: {img_count} images ({', '.join(parts)})")
            if len(to_upload) > 15:
                print(f'  ... and {len(to_upload) - 15} more')

            if unmatched:
                print(f'\nUnmatched folders (first 10):')
                for name in unmatched[:10]:
                    print(f'  {name}')

            return {'to_upload': len(to_upload), 'unmatched': len(unmatched)}

        # Actually upload
        print('\n' + '='*50)
        print('UPLOADING')
        print('='*50)

        uploaded = 0
        failed = 0

        for i, item in enumerate(to_upload):
            print(f"\n[{i+1}/{len(to_upload)}] {item['ingredient']}")

            urls = {
                'hero': None, 'field': None,
                'gallery3': None, 'gallery4': None, 'gallery5': None, 'gallery6': None
            }

            # Upload each image slot
            slot_names = {
                'hero': 'hero',
                'field': 'field',
                'gallery3': 'gallery-3',
                'gallery4': 'gallery-4',
                'gallery5': 'gallery-5',
                'gallery6': 'gallery-6'
            }

            for slot, display_name in slot_names.items():
                if item.get(slot):
                    print(f"  Uploading {display_name}: {item[slot].name[:35]}...")
                    result = self.upload_asset(item[slot])
                    if result.get('url'):
                        urls[slot] = result['url']
                        print(f"    ✓ Uploaded")
                    else:
                        print(f"    ✗ Failed: {result.get('message', 'unknown')[:50]}")

            # Update ingredient with all URLs
            has_any_url = any(urls.values())
            if has_any_url:
                if self.update_ingredient_images(
                    item['item_id'],
                    hero_url=urls['hero'],
                    field_url=urls['field'],
                    gallery3_url=urls['gallery3'],
                    gallery4_url=urls['gallery4'],
                    gallery5_url=urls['gallery5'],
                    gallery6_url=urls['gallery6']
                ):
                    uploaded += 1
                    print(f"  ✓ Updated ingredient")
                else:
                    failed += 1
                    print(f"  ✗ Failed to update ingredient")

        print('\n' + '='*50)
        print('COMPLETE')
        print('='*50)
        print(f'Uploaded: {uploaded}')
        print(f'Failed: {failed}')

        return {'uploaded': uploaded, 'failed': failed}


if __name__ == '__main__':
    folder = os.path.expanduser('~/Downloads/ingredient_images_master')
    dry_run = '--upload' not in sys.argv
    limit = None

    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    print('='*50)
    print('SMART IMAGE UPLOADER')
    print('='*50)
    print()

    uploader = SmartImageUploader()
    result = uploader.process_organized_folder(folder, dry_run=dry_run, limit=limit)

    if dry_run:
        print('\nTo upload, run:')
        print('  python3 smart_image_upload.py --upload')
        print('  python3 smart_image_upload.py --upload --limit=5  # Test first')
