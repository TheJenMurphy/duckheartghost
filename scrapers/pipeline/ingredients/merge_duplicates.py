"""
Merge duplicate ingredients in Webflow CMS.

For each duplicate:
1. Find all entries with the same name
2. Merge data (keep best/most complete data from each)
3. Update product references to point to the kept entry
4. Delete the duplicate entries
"""

import os
import time
from pathlib import Path
from collections import defaultdict

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import requests

WEBFLOW_API_BASE = "https://api.webflow.com/v2"

# Junk names to skip (not real ingredients)
JUNK_NAMES = {
    'EXT', 'PHARMACEUTICAL SECONDARY STANDARD', '●  OILS', '● OILS',
    '1', '2', '3', '3S', 'PHARMAGRADE', 'POWDER', 'MIXTURE OF ISOMERS', 'PURISS',
}


class WebflowMerger:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.site_id = os.environ.get('WEBFLOW_SITE_ID', '')
        self.ingredients_collection_id = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')
        self.products_collection_id = os.environ.get('WEBFLOW_COLLECTION_ID', '')  # Products collection

        if not self.api_token:
            raise ValueError("WEBFLOW_API_TOKEN not set")
        if not self.ingredients_collection_id:
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
            elif method == 'PATCH':
                resp = self.session.patch(url, json=data)
            else:
                raise ValueError(f'Unknown method: {method}')

            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 60))
                print(f'Rate limited. Waiting {wait}s...')
                time.sleep(wait)
                return self._request(method, endpoint, data)

            if not resp.ok:
                print(f'API Error {resp.status_code}: {resp.text[:300]}')
                return None

            return resp.json() if resp.text else {}

        except requests.RequestException as e:
            print(f'Request error: {e}')
            return None

    def get_all_items(self, collection_id):
        """Fetch all items from a collection."""
        items = []
        offset = 0
        limit = 100

        while True:
            result = self._request('GET', f'/collections/{collection_id}/items?limit={limit}&offset={offset}')
            if not result or not result.get('items'):
                break

            items.extend(result['items'])
            if len(result['items']) < limit:
                break
            offset += limit

        return items

    def find_duplicates(self, items):
        """Group items by name to find duplicates."""
        by_name = defaultdict(list)
        for item in items:
            name = item.get('fieldData', {}).get('name', '')
            if name and name not in JUNK_NAMES:
                by_name[name].append(item)

        # Return only names with multiple entries
        return {name: entries for name, entries in by_name.items() if len(entries) > 1}

    def score_item_completeness(self, item):
        """Score how complete an item's data is (higher = better)."""
        fields = item.get('fieldData', {})
        score = 0

        # Key fields worth more points
        important_fields = [
            'inci', 'also-known-as', 'plant-family', 'type-i-e-mineral-vitamin-botanical-synthetic-plant-derived-synthetic',
            'what-it-is-common-name-inci-akas-type-form-plant-family-cas-ec-origin-brief-description',
            'how-it-s-made', 'who-it-s-for-skin-types-safety-approvals-safety-warnings-safety-contraindications',
            'how-we-know-references-mla-citations', 'functions-3', 'form-3',
            'stars-attributes', 'source-attributes', 'safety-attributes', 'support-attributes',
            'suitability-attributes', 'structure-attributes', 'substance-attributes', 'sustainability-attributes',
            'gentle-score', 'skeptic-score', 'family-score',
        ]

        for field in important_fields:
            value = fields.get(field)
            if value:
                if isinstance(value, str) and len(value) > 10:
                    score += 2  # Longer content = better
                elif value:
                    score += 1

        # Bonus for images
        if fields.get('hero-image'):
            score += 5
        if fields.get('in-the-field-image'):
            score += 5

        return score

    def merge_field_data(self, items):
        """
        Merge field data from multiple items, keeping best data for each field.
        Returns merged fieldData dict.
        """
        merged = {}

        # Collect all field values
        all_fields = set()
        for item in items:
            all_fields.update(item.get('fieldData', {}).keys())

        for field in all_fields:
            best_value = None
            best_length = 0

            for item in items:
                value = item.get('fieldData', {}).get(field)
                if value:
                    # For strings, prefer longer content
                    if isinstance(value, str):
                        if len(value) > best_length:
                            best_value = value
                            best_length = len(value)
                    # For numbers, prefer non-zero
                    elif isinstance(value, (int, float)):
                        if best_value is None or (value != 0 and best_value == 0):
                            best_value = value
                            best_length = 1
                    # For dicts (like images), prefer non-empty
                    elif isinstance(value, dict):
                        if value.get('url') and not best_value:
                            best_value = value
                            best_length = 1
                    # For other types, just take first non-null
                    elif best_value is None:
                        best_value = value
                        best_length = 1

            if best_value is not None:
                merged[field] = best_value

        return merged

    def update_item(self, collection_id, item_id, field_data):
        """Update an item's field data."""
        data = {'fieldData': field_data}
        return self._request('PATCH', f'/collections/{collection_id}/items/{item_id}', data)

    def delete_item(self, collection_id, item_id):
        """Delete an item."""
        return self._request('DELETE', f'/collections/{collection_id}/items/{item_id}')

    def get_products_referencing(self, ingredient_id):
        """Find products that reference a specific ingredient."""
        # This would require scanning all products - expensive operation
        # For now, we'll handle conflicts when they arise during deletion
        pass

    def update_product_references(self, old_id, new_id):
        """
        Update product ingredient references from old_id to new_id.

        Products have a multi-reference field 'ingredients-2' linking to ingredients.
        """
        if not self.products_collection_id:
            print("    Warning: Products collection ID not set, skipping reference updates")
            return 0

        print(f"    Scanning products for references to {old_id[:8]}...")
        products = self.get_all_items(self.products_collection_id)
        updated = 0

        for product in products:
            ingredients = product.get('fieldData', {}).get('ingredients-2', [])
            if old_id in ingredients:
                # Replace old_id with new_id
                new_ingredients = [new_id if x == old_id else x for x in ingredients]
                # Remove duplicates while preserving order
                seen = set()
                new_ingredients = [x for x in new_ingredients if not (x in seen or seen.add(x))]

                result = self.update_item(
                    self.products_collection_id,
                    product['id'],
                    {'ingredients-2': new_ingredients}
                )
                if result:
                    updated += 1
                    print(f"    Updated product: {product.get('fieldData', {}).get('name', 'Unknown')}")

        return updated

    def merge_duplicates(self, dry_run=True):
        """
        Find and merge all duplicate ingredients.
        """
        print('Fetching all ingredients...')
        items = self.get_all_items(self.ingredients_collection_id)
        print(f'Total ingredients: {len(items)}')

        print('\nFinding duplicates...')
        duplicates = self.find_duplicates(items)
        print(f'Found {len(duplicates)} duplicate names ({sum(len(v) for v in duplicates.values())} total items)')

        if not duplicates:
            print('No duplicates to merge!')
            return {'merged': 0, 'deleted': 0}

        # Show what we found
        print('\nDuplicates to merge:')
        for name, entries in sorted(duplicates.items()):
            print(f'  {len(entries)}x: {name}')

        if dry_run:
            print('\n[DRY RUN] No changes made. Run with --merge to actually merge.')
            return {'merged': 0, 'deleted': 0, 'found': len(duplicates)}

        print('\n' + '=' * 50)
        print('MERGING DUPLICATES')
        print('=' * 50)

        merged_count = 0
        deleted_count = 0
        failed_count = 0

        for name, entries in duplicates.items():
            print(f'\n[{merged_count + 1}/{len(duplicates)}] Merging: {name}')

            # Score each entry
            scored = [(self.score_item_completeness(e), e) for e in entries]
            scored.sort(key=lambda x: -x[0])  # Sort by score descending

            # Keep the best one, merge data from others
            best = scored[0][1]
            others = [e for _, e in scored[1:]]

            print(f'  Keeping: {best["id"][:8]}... (score: {scored[0][0]})')
            for score, entry in scored[1:]:
                print(f'  Merging from: {entry["id"][:8]}... (score: {score})')

            # Merge field data
            merged_data = self.merge_field_data(entries)

            # Update the best entry with merged data
            # Remove fields that can't be updated (like slug, name)
            update_data = {k: v for k, v in merged_data.items() if k not in ['slug']}

            result = self.update_item(self.ingredients_collection_id, best['id'], update_data)
            if not result:
                print(f'  Failed to update merged entry!')
                failed_count += 1
                continue

            print(f'  Updated merged entry with combined data')
            merged_count += 1

            # Update product references and delete others
            for other in others:
                # Update any product references
                updated_refs = self.update_product_references(other['id'], best['id'])
                if updated_refs:
                    print(f'  Updated {updated_refs} product references')

                # Delete the duplicate
                result = self.delete_item(self.ingredients_collection_id, other['id'])
                if result is not None:
                    deleted_count += 1
                    print(f'  Deleted: {other["id"][:8]}...')
                else:
                    print(f'  Failed to delete: {other["id"][:8]}... (may still have references)')

        print('\n' + '=' * 50)
        print('MERGE COMPLETE')
        print('=' * 50)
        print(f'Duplicate groups merged: {merged_count}')
        print(f'Entries deleted: {deleted_count}')
        print(f'Failed: {failed_count}')

        return {'merged': merged_count, 'deleted': deleted_count, 'failed': failed_count}


if __name__ == '__main__':
    import sys

    dry_run = '--merge' not in sys.argv

    print('=' * 50)
    print('WEBFLOW INGREDIENT DUPLICATE MERGER')
    print('=' * 50)
    print()

    merger = WebflowMerger()
    result = merger.merge_duplicates(dry_run=dry_run)

    if dry_run and result.get('found', 0) > 0:
        print()
        print('To actually merge these duplicates, run:')
        print('  python3 merge_duplicates.py --merge')
