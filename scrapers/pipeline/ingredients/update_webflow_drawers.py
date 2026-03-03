"""
Update Webflow ingredient drawer content with CosIng enriched data.

Drawer Fields:
1. what-it-is - INCI, CAS, EC, Type, Description
2. how-it-s-made - Chemistry, molecular info
3. who-it-s-for - Skin types, safety, warnings
4. how-we-know - References, SCCS opinions
5. functions-3 - Functions (plain text)
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


def infer_type(inci_name: str, functions: str) -> str:
    """Infer ingredient type from name and functions."""
    name_lower = (inci_name or '').lower()

    if any(kw in name_lower for kw in ['extract', 'flower', 'leaf', 'root', 'bark', 'seed', 'fruit', 'peel']):
        return "Botanical"
    if any(x in name_lower for x in ['vitamin ', 'retinol', 'tocopherol', 'ascorb', 'niacin', 'panthen']):
        return "Vitamin"
    if any(x in name_lower for x in ['mica', 'silica', 'zinc oxide', 'titanium dioxide', 'water', 'aqua']):
        return "Mineral"
    if any(x in name_lower for x in ['ferment', 'lactobacillus', 'saccharomyces', 'biosaccharide']):
        return "Fermented"
    if any(x in name_lower for x in [' oil', 'seed oil', 'kernel oil', 'butter', ' wax', ' cera']):
        return "Plant-Derived"
    if any(x in name_lower for x in ['dimethicone', 'silicone', 'peg-', 'ppg-', 'acrylate', 'polymer']):
        return "Synthetic"
    return "Synthetic"


def infer_form(inci_name: str) -> str:
    """Infer ingredient form from name."""
    name_lower = (inci_name or '').lower()

    if any(x in name_lower for x in [' oil', 'seed oil', 'kernel oil', 'fruit oil']):
        return "Oil"
    if any(x in name_lower for x in [' butter', 'shea butter', 'cocoa butter']):
        return "Butter"
    if any(x in name_lower for x in [' wax', 'beeswax', 'candelilla', ' cera']):
        return "Wax"
    if any(x in name_lower for x in [' powder', 'mica', 'talc', 'silica', 'kaolin', 'clay', 'oxide']):
        return "Powder"
    if any(x in name_lower for x in [' extract', 'leaf extract', 'root extract', 'flower extract']):
        return "Extract"
    if any(x in name_lower for x in ['water', 'aqua', 'hydrosol', 'flower water']):
        return "Liquid"
    if any(x in name_lower for x in ['glycerin', 'glycerol', 'propanediol', 'alcohol', 'dimethicone']):
        return "Liquid"
    if any(x in name_lower for x in ['acid']):
        return "Powder/Crystal"
    return None


def build_what_it_is(row: Dict) -> str:
    """Build the 'What It Is' drawer content."""
    inci_name = row.get('inci_name', '')
    cas_no = row.get('cas_no', '')
    description = row.get('chemical_description', '')
    functions = row.get('functions', '')

    ing_type = infer_type(inci_name, functions)
    form = infer_form(inci_name)

    parts = []

    # INCI Name
    parts.append(f"<p><strong>INCI Name:</strong> <em>{inci_name}</em></p>")

    # Type
    parts.append(f"<p><strong>Type:</strong> {ing_type}</p>")

    # Form
    if form:
        parts.append(f"<p><strong>Form:</strong> {form}</p>")

    # CAS Number
    if cas_no:
        parts.append(f"<p><strong>CAS Number:</strong> {cas_no}</p>")

    # Description
    if description:
        # Clean and truncate description
        desc = description.strip()
        if len(desc) > 500:
            desc = desc[:497] + "..."
        parts.append(f"<p><strong>Description:</strong> {desc}</p>")

    return ''.join(parts) if parts else ''


def build_how_its_made(row: Dict) -> str:
    """Build the 'How It's Made' drawer content."""
    description = row.get('chemical_description', '')
    functions = row.get('functions', '')
    inci_name = row.get('inci_name', '')

    parts = []

    # Infer origin/process from name and description
    name_lower = inci_name.lower()
    desc_lower = (description or '').lower()

    # Origin/Source
    if any(x in name_lower for x in ['extract', 'oil', 'butter', 'wax']):
        if 'seed' in name_lower:
            parts.append("<p><strong>Source:</strong> Extracted from seeds</p>")
        elif 'flower' in name_lower:
            parts.append("<p><strong>Source:</strong> Extracted from flowers</p>")
        elif 'leaf' in name_lower:
            parts.append("<p><strong>Source:</strong> Extracted from leaves</p>")
        elif 'root' in name_lower:
            parts.append("<p><strong>Source:</strong> Extracted from roots</p>")
        elif 'fruit' in name_lower:
            parts.append("<p><strong>Source:</strong> Extracted from fruit</p>")
        elif 'bark' in name_lower:
            parts.append("<p><strong>Source:</strong> Extracted from bark</p>")

    if 'ferment' in name_lower or 'lactobacillus' in name_lower:
        parts.append("<p><strong>Process:</strong> Produced through fermentation</p>")

    if 'synthetic' in desc_lower or 'conforms to the formula' in desc_lower:
        parts.append("<p><strong>Process:</strong> Synthetically produced</p>")

    # Chemical info from description
    if description and ('formula' in desc_lower or 'molecular' in desc_lower or 'polymer' in desc_lower):
        # Extract just the chemical classification part
        if len(description) > 300:
            chem_desc = description[:297] + "..."
        else:
            chem_desc = description
        parts.append(f"<p><strong>Chemistry:</strong> {chem_desc}</p>")

    return ''.join(parts) if parts else ''


def build_who_its_for(row: Dict) -> str:
    """Build the 'Who It's For' drawer content."""
    suitable_for = row.get('suitable_for', '')
    skin_concerns = row.get('skin_concerns', '')
    sensitive_safe = row.get('sensitive_safe', '')
    eu_annexes = row.get('eu_annexes', '')
    usage_conditions = row.get('usage_conditions', '')
    max_general = row.get('max_general_pct', '')
    max_professional = row.get('max_professional_pct', '')

    parts = []

    # Skin Types
    if suitable_for:
        parts.append(f"<p><strong>Best For:</strong> {suitable_for}</p>")

    # Concerns
    if skin_concerns:
        parts.append(f"<p><strong>Addresses:</strong> {skin_concerns}</p>")

    # Sensitive skin
    if sensitive_safe == 'Yes':
        parts.append("<p><strong>Sensitive Skin:</strong> Generally safe for sensitive skin</p>")
    elif sensitive_safe == 'No':
        parts.append("<p><strong>Sensitive Skin:</strong> May not be suitable - check restrictions below</p>")

    # Safety warnings
    warnings = []
    if eu_annexes:
        if 'II' in eu_annexes:
            warnings.append("EU Prohibited substance")
        if 'III' in eu_annexes:
            warnings.append("EU Restricted - concentration limits apply")
        if 'IV' in eu_annexes:
            warnings.append("EU Colorant - restricted use")
        if 'V' in eu_annexes:
            warnings.append("EU Preservative - restricted use")
        if 'VI' in eu_annexes:
            warnings.append("EU UV Filter - restricted use")

    if warnings:
        parts.append(f"<p><strong>Regulatory Status:</strong> {'; '.join(warnings)}</p>")

    # Concentration limits
    if max_general or max_professional:
        conc_parts = []
        if max_general:
            conc_parts.append(f"General use: max {max_general}%")
        if max_professional:
            conc_parts.append(f"Professional use: max {max_professional}%")
        parts.append(f"<p><strong>Max Concentration:</strong> {' | '.join(conc_parts)}</p>")

    # Usage conditions/warnings
    if usage_conditions:
        # Clean and truncate
        conditions = usage_conditions.strip()
        if len(conditions) > 400:
            conditions = conditions[:397] + "..."
        parts.append(f"<p><strong>Usage Conditions:</strong> {conditions}</p>")

    return ''.join(parts) if parts else ''


def build_how_we_know(row: Dict) -> str:
    """Build the 'How We Know' drawer content with references."""
    sccs_opinions = row.get('sccs_opinions', '')
    eu_annexes = row.get('eu_annexes', '')
    cas_no = row.get('cas_no', '')
    cosing_id = row.get('cosing_id', '')

    parts = []

    # CosIng reference
    if cosing_id:
        parts.append(f"<p><strong>CosIng Database:</strong> Reference #{cosing_id}</p>")
        parts.append(f'<p><a href="https://ec.europa.eu/growth/tools-databases/cosing/" target="_blank">EU CosIng Database</a></p>')

    # SCCS Opinions
    if sccs_opinions:
        # Split and format opinions
        opinions = sccs_opinions.split(' | ')
        if len(opinions) > 3:
            opinions = opinions[:3]
            opinions.append("...")
        parts.append(f"<p><strong>SCCS Opinions:</strong></p>")
        parts.append("<ul>")
        for op in opinions:
            if op and op != "...":
                parts.append(f"<li>{op}</li>")
            elif op == "...":
                parts.append("<li><em>Additional opinions available</em></li>")
        parts.append("</ul>")

    # EU Regulatory references
    if eu_annexes:
        parts.append(f"<p><strong>EU Cosmetics Regulation:</strong> Listed in Annex {eu_annexes}</p>")

    # PubChem link for CAS numbers
    if cas_no and '/' not in cas_no:  # Single CAS number
        parts.append(f'<p><strong>PubChem:</strong> <a href="https://pubchem.ncbi.nlm.nih.gov/#query={cas_no}" target="_blank">Search {cas_no}</a></p>')

    return ''.join(parts) if parts else ''


class WebflowDrawerUpdater:
    """Updates Webflow ingredient drawer fields."""

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
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request
        if elapsed < 1.0:
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

    def build_drawer_fields(self, row: Dict) -> Dict:
        """Build all drawer field content from CSV row."""
        fields = {}

        # What It Is drawer
        what_it_is = build_what_it_is(row)
        if what_it_is:
            fields['what-it-is-common-name-inci-akas-type-form-plant-family-cas-ec-origin-brief-description'] = what_it_is

        # How It's Made drawer
        how_made = build_how_its_made(row)
        if how_made:
            fields['how-it-s-made'] = how_made

        # Who It's For drawer
        who_for = build_who_its_for(row)
        if who_for:
            fields['who-it-s-for-skin-types-safety-approvals-safety-warnings-safety-contraindications'] = who_for

        # How We Know drawer
        how_know = build_how_we_know(row)
        if how_know:
            fields['how-we-know-references-mla-citations'] = how_know

        # Type field
        ing_type = infer_type(row.get('inci_name', ''), row.get('functions', ''))
        fields['type-i-e-mineral-vitamin-botanical-synthetic-plant-derived-synthetic'] = ing_type.lower()

        # Form field
        form = infer_form(row.get('inci_name', ''))
        if form:
            fields['form-3'] = form.lower()

        return fields

    def update_from_csv(self, limit: int = None):
        """Update Webflow drawer fields from the 9S mapped CSV."""
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
            'skipped_no_content': 0,
        }

        print(f"Updating drawer content for {len(ingredients)} ingredients...")

        for i, ing in enumerate(ingredients):
            if not ing.webflow_id:
                continue

            # Find in CSV data
            csv_row = csv_data.get(ing.inci_name.lower())

            if not csv_row:
                stats['not_in_csv'] += 1
                continue

            # Build drawer fields
            fields = self.build_drawer_fields(csv_row)

            if not fields:
                stats['skipped_no_content'] += 1
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
        print("DRAWER UPDATE COMPLETE")
        print('='*40)
        print(f"Total: {stats['total']}")
        print(f"Updated: {stats['updated']}")
        print(f"Not in CSV: {stats['not_in_csv']}")
        print(f"Skipped (no content): {stats['skipped_no_content']}")
        print(f"Failed: {stats['failed']}")

        return stats


def main():
    import sys

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    updater = WebflowDrawerUpdater()
    updater.update_from_csv(limit=limit)


if __name__ == '__main__':
    main()
