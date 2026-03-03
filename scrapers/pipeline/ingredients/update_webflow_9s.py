"""
Update existing Webflow ingredients with new 9S mapped data.

Reads the enriched CSV and patches existing Webflow items.
"""

import csv
import os
import re
import time
from pathlib import Path
from typing import Dict, Optional

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import requests

from .database import IngredientDatabase

# Paths
CSV_FILE = Path(__file__).parent.parent / "data" / "cosing_9s_mapped.csv"
WEBFLOW_API_BASE = "https://api.webflow.com/v2"


def slugify(name: str) -> str:
    """Convert INCI name to URL-safe slug."""
    if not name:
        return ""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    slug = re.sub(r'-+', '-', slug)
    return slug[:100]


def infer_type(inci_name: str, functions: str) -> str:
    """Infer ingredient type from name and functions."""
    name_lower = (inci_name or '').lower()

    botanical_keywords = ['extract', 'flower', 'leaf', 'root', 'bark', 'seed', 'fruit', 'peel']
    if any(kw in name_lower for kw in botanical_keywords):
        return "botanical"
    if any(x in name_lower for x in ['vitamin ', 'retinol', 'tocopherol', 'ascorb', 'niacin', 'panthen']):
        return "vitamin"
    if any(x in name_lower for x in ['mica', 'silica', 'zinc oxide', 'titanium dioxide', 'water', 'aqua']):
        return "mineral"
    if any(x in name_lower for x in ['ferment', 'lactobacillus', 'saccharomyces', 'biosaccharide']):
        return "fermented"
    if any(x in name_lower for x in [' oil', 'seed oil', 'kernel oil', 'butter', ' wax', ' cera']):
        return "plant-derived"
    if any(x in name_lower for x in ['dimethicone', 'silicone', 'peg-', 'ppg-', 'acrylate', 'polymer']):
        return "synthetic"
    return "synthetic"


def map_support_attributes(functions: str, benefits: str) -> str:
    """Map functions/benefits to support attribute slugs."""
    attrs = []
    combined = (functions + ' ' + benefits).lower()

    if any(x in combined for x in ['moistur', 'hydrat', 'humectant', 'emollient']):
        attrs.append("moisturizing")
    if any(x in combined for x in ['anti-aging', 'antiaging', 'antioxidant']):
        attrs.append("antiaging")
    if any(x in combined for x in ['brighten', 'lighten', 'radian', 'bleach']):
        attrs.append("brightening")
    if any(x in combined for x in ['sooth', 'calm', 'anti-inflam', 'refresh']):
        attrs.append("soothing")
    if any(x in combined for x in ['exfolia', 'peel', 'keratolytic', 'abrasive']):
        attrs.append("exfoliating")
    if any(x in combined for x in ['protect', 'barrier', 'film forming', 'shield']):
        attrs.append("nourishing-protecting")
    if any(x in combined for x in ['oil control', 'mattif', 'sebum', 'absorbent']):
        attrs.append("oil-control")
    if any(x in combined for x in ['nourish', 'repair', 'conditioning']):
        attrs.append("nourishing-protecting")
    if any(x in combined for x in ['clarif', 'pore', 'acne', 'antimicrobial', 'cleansing']):
        attrs.append("clarifying")
    if any(x in combined for x in ['sunscreen', 'uv absorber', 'uv filter', 'sun-protect']):
        attrs.append("spf")

    return ', '.join(list(set(attrs))) if attrs else ''


def map_suitability_attributes(suitable_for: str, sensitive_safe: str, skin_concerns: str) -> str:
    """Map skin suitability to attribute slugs."""
    attrs = []
    combined = (suitable_for + ' ' + (skin_concerns or '')).lower()

    if 'all skin types' in combined:
        attrs.append("all-skin-types")
    if sensitive_safe == 'Yes' or 'sensitive' in combined:
        attrs.append("gentle")
    if 'dry' in combined:
        attrs.append("skin-types")
    if 'oily' in combined:
        attrs.append("skin-types")
    if 'aging' in combined:
        attrs.append("skin-types")

    return ', '.join(list(set(attrs))) if attrs else ''


def map_safety_attributes(sensitive_safe: str, eu_annexes: str, max_conc: str) -> str:
    """Map safety info to attribute slugs."""
    attrs = []

    if sensitive_safe == 'Yes':
        attrs.append("all-shades-safe")
    if sensitive_safe == 'No':
        attrs.append("eu-restricted")

    if eu_annexes:
        if 'II' in eu_annexes:
            attrs.append("eu-prohibited")
        if 'III' in eu_annexes:
            attrs.append("eu-restricted")
        if 'IV' in eu_annexes:
            attrs.append("eu-colorant-restricted")
        if 'V' in eu_annexes:
            attrs.append("eu-preservative-restricted")

    if max_conc:
        attrs.append("concentration-limits")

    return ', '.join(list(set(attrs))) if attrs else ''


def map_source_attributes(inci_name: str, ing_type: str) -> str:
    """Map source type to attribute slugs."""
    attrs = []
    name_lower = inci_name.lower()

    if ing_type in ("botanical", "plant-derived"):
        attrs.append("plant-derived")
    elif ing_type == "mineral":
        attrs.append("mineral")
    elif ing_type == "fermented":
        attrs.append("fermented")
    elif ing_type == "vitamin":
        attrs.append("vitamin")
    elif ing_type == "synthetic":
        attrs.append("synthetic")

    if any(x in name_lower for x in ['algae', 'seaweed', 'kelp', 'marine']):
        attrs.append("marine")

    return ', '.join(list(set(attrs))) if attrs else ''


def map_substance_attributes(functions: str) -> str:
    """Map functions to substance type attributes."""
    attrs = []
    func_lower = (functions or '').lower()

    if 'preservative' in func_lower:
        attrs.append("key-ingredients")
    if 'fragrance' in func_lower or 'perfum' in func_lower:
        attrs.append("key-ingredients")
    if 'surfactant' in func_lower:
        attrs.append("base-ingredients")
    if 'colorant' in func_lower or 'hair dyeing' in func_lower:
        attrs.append("key-ingredients")
    if 'antioxidant' in func_lower or 'uv' in func_lower:
        attrs.append("key-ingredients")
    if 'emollient' in func_lower or 'solvent' in func_lower:
        attrs.append("base-ingredients")

    return ', '.join(list(set(attrs))) if attrs else 'base-ingredients'


class WebflowUpdater:
    """Updates existing Webflow items with 9S data."""

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
        self.db = IngredientDatabase()

    def _rate_limit(self):
        """Enforce rate limiting - 60 req/min."""
        elapsed = time.time() - self._last_request
        if elapsed < 1.0:  # 1 second between requests to be safe
            time.sleep(1.0 - elapsed)
        self._last_request = time.time()

    def _request(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """Make API request."""
        self._rate_limit()

        url = f'{WEBFLOW_API_BASE}{endpoint}'

        try:
            if method == 'PATCH':
                resp = self.session.patch(url, json=data)
            elif method == 'GET':
                resp = self.session.get(url)
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

    def update_item(self, item_id: str, fields: Dict) -> bool:
        """Update a Webflow item."""
        data = {'fieldData': fields}
        result = self._request('PATCH', f'/collections/{self.collection_id}/items/{item_id}', data)
        return result is not None

    def build_9s_fields(self, row: Dict) -> Dict:
        """Build 9S field data from CSV row."""
        inci_name = row.get('inci_name', '')
        functions = row.get('functions', '')
        benefits = row.get('benefits', '')
        features = row.get('features', '')
        suitable_for = row.get('suitable_for', '')
        skin_concerns = row.get('skin_concerns', '')
        sensitive_safe = row.get('sensitive_safe', '')
        eu_annexes = row.get('eu_annexes', '')
        max_general = row.get('max_general_pct', '')
        max_professional = row.get('max_professional_pct', '')
        chemical_desc = row.get('chemical_description', '')

        ing_type = infer_type(inci_name, functions)

        fields = {
            # Functions
            'functions-3': functions,

            # Type
            'type-i-e-mineral-vitamin-botanical-synthetic-plant-derived-synthetic': ing_type,

            # SUPPORT
            'support-attributes': map_support_attributes(functions, benefits),
            'support-details': f"Functions: {functions} | Benefits: {benefits} | Features: {features}" if functions else '',

            # SUITABILITY
            'suitability-attributes': map_suitability_attributes(suitable_for, sensitive_safe, skin_concerns),
            'suitability-details': f"Skin Types: {suitable_for}" + (f" | Concerns: {skin_concerns}" if skin_concerns else ''),

            # SAFETY
            'safety-attributes': map_safety_attributes(sensitive_safe, eu_annexes, max_general),
            'safety-details': (f"EU Regulatory: {eu_annexes}" if eu_annexes else '') +
                             (f" | Max: {max_general}%" if max_general else ''),

            # SOURCE
            'source-attributes': map_source_attributes(inci_name, ing_type),
            'source-details': f"Type: {ing_type.title()}",

            # SUBSTANCE
            'substance-attributes': map_substance_attributes(functions),
            'substance-details': f"Functions: {functions}" if functions else '',

            # SPEND (concentrations)
            'spend-attributes': 'concentration-limits' if max_general else '',
            'spend-details': (f"Max General: {max_general}%" if max_general else '') +
                            (f" | Max Professional: {max_professional}%" if max_professional else ''),
        }

        # Add CAS if present
        if row.get('cas_no'):
            fields['cas-2'] = row.get('cas_no')

        # Clean empty values
        return {k: v for k, v in fields.items() if v}

    def update_from_csv(self, limit: int = None):
        """Update Webflow items from the 9S mapped CSV."""
        print(f"Loading CSV from {CSV_FILE}...")

        # Load CSV data
        csv_data = {}
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                inci = row.get('inci_name', '').strip()
                if inci:
                    csv_data[inci.lower()] = row

        print(f"Loaded {len(csv_data)} ingredients from CSV")

        # Get all ingredients from database with webflow_id
        ingredients = self.db.get_all(limit=limit)

        stats = {
            'total': len(ingredients),
            'updated': 0,
            'not_in_csv': 0,
            'failed': 0,
        }

        print(f"Updating {len(ingredients)} Webflow items...")

        for i, ing in enumerate(ingredients):
            if not ing.webflow_id:
                continue

            # Find in CSV data
            csv_row = csv_data.get(ing.inci_name.lower())

            if not csv_row:
                stats['not_in_csv'] += 1
                continue

            # Build update fields
            fields = self.build_9s_fields(csv_row)

            if not fields:
                continue

            # Update Webflow
            if self.update_item(ing.webflow_id, fields):
                stats['updated'] += 1
                if (i + 1) % 10 == 0:
                    print(f"  [{i+1}/{len(ingredients)}] Updated: {ing.inci_name[:40]}")
            else:
                stats['failed'] += 1
                print(f"  Failed: {ing.inci_name}")

        print(f"\n{'='*40}")
        print("UPDATE COMPLETE")
        print('='*40)
        print(f"Total: {stats['total']}")
        print(f"Updated: {stats['updated']}")
        print(f"Not in CSV: {stats['not_in_csv']}")
        print(f"Failed: {stats['failed']}")

        return stats


def main():
    import sys

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    updater = WebflowUpdater()
    updater.update_from_csv(limit=limit)


if __name__ == '__main__':
    main()
