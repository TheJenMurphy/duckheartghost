#!/usr/bin/env python3
"""
Sync enhanced ingredient data from CSV to Webflow.

Usage:
    python csv_sync.py /path/to/ingredients_enhanced_clean_scores.csv --limit 100
    python csv_sync.py /path/to/ingredients_enhanced_clean_scores.csv --all
"""

import csv
import os
import sys
import time
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import requests

# Webflow API
WEBFLOW_API_BASE = "https://api.webflow.com/v2"


class CSVToWebflowSync:
    """Sync CSV ingredient data directly to Webflow."""

    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.collection_id = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

        self._last_request = 0

        # Cache of slug -> webflow_id
        self._item_cache = {}

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_request = time.time()

    def _request(self, method, endpoint, data=None):
        """Make API request with error handling."""
        self._rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'

        try:
            if method == 'GET':
                resp = self.session.get(url)
            elif method == 'PATCH':
                resp = self.session.patch(url, json=data)
            else:
                return None

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

    def _slugify(self, name):
        """Convert name to slug."""
        import re
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')[:100]

    def find_item_by_slug(self, slug):
        """Find Webflow item by slug."""
        if slug in self._item_cache:
            return self._item_cache[slug]

        result = self._request('GET', f'/collections/{self.collection_id}/items?slug={slug}')
        if result and result.get('items'):
            item_id = result['items'][0].get('id')
            self._item_cache[slug] = item_id
            return item_id
        return None

    def csv_row_to_fields(self, row):
        """Convert CSV row to Webflow fields."""
        fields = {}

        # Clean Score (1-5) -> Ingredient Safety Score number field + stars
        clean_score = row.get('Clean_Score', '')
        if clean_score:
            try:
                score = int(clean_score)
                # Set the number field directly
                fields['ingredient-safety-score'] = score

                # Map to stars attributes
                if score >= 4:
                    fields['stars-attributes'] = '5-out-of-5, scientific-backing'
                elif score == 3:
                    fields['stars-attributes'] = '4-out-of-5'
                elif score == 2:
                    fields['stars-attributes'] = '3-out-of-5'
                else:
                    fields['stars-attributes'] = '2-out-of-5'
                fields['stars-details'] = f"Clean Score: {score}/5 | {row.get('Reasoning', '')}"
            except ValueError:
                pass

        # Substance Types -> substance-attributes and Type field
        substance_types = row.get('Substance_Types', '')
        if substance_types:
            # Map to substance attributes
            attrs = []
            types_lower = substance_types.lower()

            if 'carrier' in types_lower:
                attrs.append('base-ingredients')
            if 'silicone' in types_lower:
                attrs.append('base-ingredients')
            if 'conditioning' in types_lower:
                attrs.append('key-ingredients')
            if 'emollient' in types_lower:
                attrs.append('key-ingredients')
            if 'humectant' in types_lower:
                attrs.append('key-ingredients')
            if 'surfactant' in types_lower:
                attrs.append('base-ingredients')
            if 'preservative' in types_lower:
                attrs.append('key-ingredients')
            if 'antioxidant' in types_lower:
                attrs.append('key-ingredients')
            if 'fragrance' in types_lower:
                attrs.append('key-ingredients')
            if 'colorant' in types_lower:
                attrs.append('key-ingredients')
            if 'exfoliant' in types_lower:
                attrs.append('key-ingredients')

            if attrs:
                fields['substance-attributes'] = ', '.join(list(set(attrs)))
            fields['substance-details'] = f"Types: {substance_types}"

            # Also set the Type field based on substance types
            if 'silicone' in types_lower:
                ing_type = 'synthetic'
            elif 'carrier' in types_lower:
                ing_type = 'plant-derived'
            elif any(x in types_lower for x in ['botanical', 'plant', 'essential oil']):
                ing_type = 'botanical'
            elif any(x in types_lower for x in ['mineral', 'oxide']):
                ing_type = 'mineral'
            elif any(x in types_lower for x in ['vitamin']):
                ing_type = 'vitamin'
            else:
                ing_type = 'synthetic'

            fields['type-i-e-mineral-vitamin-botanical-synthetic-plant-derived-synthetic'] = ing_type

        # Fragrance Type
        fragrance_type = row.get('Fragrance_Type', '')
        if fragrance_type:
            fields['scent'] = f"<p>{fragrance_type}</p>"

        # Safety Details
        safety_details = row.get('Safety_Details', '')
        if safety_details:
            fields['safety-details'] = safety_details

        # Safety Concerns
        safety_concerns = row.get('Safety_Concerns', '')
        if safety_concerns:
            fields['safety-ratings-contraindications-2'] = safety_concerns

        # Suitability
        suitability = row.get('Suitability', '')
        if suitability:
            fields['suitability-attributes'] = suitability
            if 'low-allergy-risk' in suitability.lower():
                fields['suitability-details'] = 'Low allergy risk, suitable for sensitive skin'

        return fields

    def sync_csv(self, csv_path, limit=None):
        """Sync CSV data to Webflow."""
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total = len(rows) if limit is None else min(limit, len(rows))
        success = 0
        fail = 0
        not_found = 0

        print(f'Syncing {total} ingredients from CSV...')
        print()

        for i, row in enumerate(rows[:total]):
            name = row.get('Name', '')
            if not name:
                continue

            slug = self._slugify(name)
            item_id = self.find_item_by_slug(slug)

            if not item_id:
                not_found += 1
                if not_found <= 10:
                    print(f'  Not found: {name}')
                continue

            fields = self.csv_row_to_fields(row)

            if fields:
                data = {'fieldData': fields}
                result = self._request('PATCH', f'/collections/{self.collection_id}/items/{item_id}', data)

                if result:
                    success += 1
                else:
                    fail += 1

            if (i + 1) % 100 == 0:
                print(f'[{i+1}/{total}] OK: {success}, Failed: {fail}, Not found: {not_found}')

        print(f'\n=== COMPLETE ===')
        print(f'Total processed: {total}')
        print(f'Success: {success}')
        print(f'Failed: {fail}')
        print(f'Not found in Webflow: {not_found}')

        return {'success': success, 'fail': fail, 'not_found': not_found}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python csv_sync.py <csv_path> [--limit N] [--all]')
        sys.exit(1)

    csv_path = sys.argv[1]
    limit = None

    if '--limit' in sys.argv:
        idx = sys.argv.index('--limit')
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])
    elif '--all' not in sys.argv:
        limit = 100  # Default to 100

    sync = CSVToWebflowSync()
    sync.sync_csv(csv_path, limit=limit)
