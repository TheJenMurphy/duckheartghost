#!/usr/bin/env python3
"""
Fetch molecular data from PubChem and populate the HOW IT'S MADE drawer.

Usage:
    python pubchem_drawer.py --limit 50
    python pubchem_drawer.py --all
"""

import os
import re
import sys
import time
import requests
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# APIs
WEBFLOW_API_BASE = "https://api.webflow.com/v2"
PUBCHEM_API_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
INGREDIENTS_COLLECTION_ID = "67b25dbc040723aed519bf6f"


class PubChemDrawerUpdater:
    """Fetch PubChem data and update ingredient drawers."""

    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')

        self.webflow_session = requests.Session()
        self.webflow_session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        })

        self._last_webflow_request = 0
        self._last_pubchem_request = 0

    def _webflow_rate_limit(self):
        elapsed = time.time() - self._last_webflow_request
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_webflow_request = time.time()

    def _pubchem_rate_limit(self):
        # PubChem allows 5 requests/second, be conservative
        elapsed = time.time() - self._last_pubchem_request
        if elapsed < 0.3:
            time.sleep(0.3 - elapsed)
        self._last_pubchem_request = time.time()

    def _webflow_request(self, method, endpoint, data=None):
        self._webflow_rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'

        try:
            if method == 'GET':
                resp = self.webflow_session.get(url)
            elif method == 'PATCH':
                resp = self.webflow_session.patch(url, json=data)
            else:
                return None

            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 60))
                print(f'Webflow rate limited. Waiting {wait}s...')
                time.sleep(wait)
                return self._webflow_request(method, endpoint, data)

            if not resp.ok:
                return None

            return resp.json() if resp.text else {}

        except requests.RequestException:
            return None

    def fetch_pubchem_data(self, ingredient_name):
        """Fetch molecular data from PubChem."""
        self._pubchem_rate_limit()

        # Clean the name for searching
        search_name = ingredient_name
        # Remove parenthetical content for search
        search_name = re.sub(r'\s*\([^)]*\)', '', search_name).strip()
        # URL encode
        search_name = requests.utils.quote(search_name)

        try:
            # First, get the compound ID
            url = f"{PUBCHEM_API_BASE}/compound/name/{search_name}/cids/JSON"
            resp = requests.get(url, timeout=10)

            if resp.status_code != 200:
                return None

            data = resp.json()
            cids = data.get('IdentifierList', {}).get('CID', [])
            if not cids:
                return None

            cid = cids[0]

            # Now fetch properties
            self._pubchem_rate_limit()
            props_url = f"{PUBCHEM_API_BASE}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,IUPACName,CanonicalSMILES,InChI/JSON"
            props_resp = requests.get(props_url, timeout=10)

            if props_resp.status_code != 200:
                return None

            props_data = props_resp.json()
            properties = props_data.get('PropertyTable', {}).get('Properties', [])

            if not properties:
                return None

            prop = properties[0]

            # Try to get description
            self._pubchem_rate_limit()
            desc_url = f"{PUBCHEM_API_BASE}/compound/cid/{cid}/description/JSON"
            desc_resp = requests.get(desc_url, timeout=10)

            description = ""
            if desc_resp.status_code == 200:
                desc_data = desc_resp.json()
                descriptions = desc_data.get('InformationList', {}).get('Information', [])
                for d in descriptions:
                    if d.get('Description'):
                        description = d['Description']
                        break

            return {
                'cid': cid,
                'molecular_formula': prop.get('MolecularFormula', ''),
                'molecular_weight': prop.get('MolecularWeight', 0),
                'iupac_name': prop.get('IUPACName', ''),
                'smiles': prop.get('CanonicalSMILES', ''),
                'inchi': prop.get('InChI', ''),
                'description': description[:500] if description else '',
            }

        except Exception as e:
            return None

    def build_how_its_made_html(self, pubchem_data):
        """Build HTML for the HOW IT'S MADE drawer."""
        parts = []

        if pubchem_data.get('molecular_formula'):
            parts.append(f"<p><strong>Molecular Formula:</strong> {pubchem_data['molecular_formula']}</p>")

        if pubchem_data.get('molecular_weight'):
            try:
                weight = float(pubchem_data['molecular_weight'])
                parts.append(f"<p><strong>Molecular Weight:</strong> {weight:.2f} g/mol</p>")
            except (ValueError, TypeError):
                parts.append(f"<p><strong>Molecular Weight:</strong> {pubchem_data['molecular_weight']} g/mol</p>")

        if pubchem_data.get('iupac_name'):
            parts.append(f"<p><strong>IUPAC Name:</strong> <em>{pubchem_data['iupac_name']}</em></p>")

        if pubchem_data.get('smiles'):
            parts.append(f"<p><strong>SMILES:</strong> <code>{pubchem_data['smiles'][:100]}</code></p>")

        if pubchem_data.get('description'):
            parts.append(f"<p><strong>Chemistry:</strong> {pubchem_data['description']}</p>")

        if pubchem_data.get('cid'):
            pubchem_url = f"https://pubchem.ncbi.nlm.nih.gov/compound/{pubchem_data['cid']}"
            parts.append(f'<p><strong>Source:</strong> <a href="{pubchem_url}">PubChem CID {pubchem_data["cid"]}</a></p>')

        return ''.join(parts)

    def get_ingredients_without_drawer(self, limit=None):
        """Get ingredients that don't have HOW IT'S MADE populated."""
        ingredients = []
        offset = 0
        batch_limit = 100

        while True:
            result = self._webflow_request('GET',
                f'/collections/{INGREDIENTS_COLLECTION_ID}/items?limit={batch_limit}&offset={offset}')

            if not result:
                break

            items = result.get('items', [])
            if not items:
                break

            for item in items:
                fd = item.get('fieldData', {})
                # Check if HOW IT'S MADE is empty
                how_made = fd.get('how-it-s-made', '')
                if not how_made or len(how_made.strip()) < 20:
                    ingredients.append(item)

            offset += batch_limit

            if len(items) < batch_limit:
                break

            if limit and len(ingredients) >= limit:
                break

        if limit:
            ingredients = ingredients[:limit]

        return ingredients

    def update_ingredient(self, item_id, how_made_html):
        """Update ingredient with HOW IT'S MADE content."""
        update_data = {
            'fieldData': {
                'how-it-s-made': how_made_html
            }
        }

        result = self._webflow_request('PATCH',
            f'/collections/{INGREDIENTS_COLLECTION_ID}/items/{item_id}',
            update_data)

        return result is not None

    def run(self, limit=None):
        """Run the PubChem drawer update process."""
        print("Fetching ingredients without HOW IT'S MADE data...")
        ingredients = self.get_ingredients_without_drawer(limit=limit)
        print(f"Found {len(ingredients)} ingredients to process")

        if not ingredients:
            print("No ingredients to process")
            return

        stats = {
            'found': 0,
            'updated': 0,
            'not_found': 0,
            'errors': 0,
        }

        print(f"\nFetching PubChem data...\n")

        for i, ingredient in enumerate(ingredients, 1):
            fd = ingredient.get('fieldData', {})
            item_id = ingredient.get('id')
            name = fd.get('name', 'Unknown')
            inci = fd.get('inci', '')

            # Clean INCI for searching (remove HTML)
            inci_clean = re.sub(r'<[^>]+>', '', inci).strip()

            # Try INCI first, then common name
            search_names = []
            if inci_clean:
                search_names.append(inci_clean)
            if name and name != inci_clean:
                search_names.append(name)

            pubchem_data = None
            for search_name in search_names:
                pubchem_data = self.fetch_pubchem_data(search_name)
                if pubchem_data:
                    break

            if pubchem_data:
                stats['found'] += 1
                html = self.build_how_its_made_html(pubchem_data)

                if self.update_ingredient(item_id, html):
                    stats['updated'] += 1
                    mw = pubchem_data.get('molecular_weight', 0)
                    try:
                        mw = float(mw)
                        print(f"  [{i}/{len(ingredients)}] {name[:40]}: Updated (MW: {mw:.1f})")
                    except:
                        print(f"  [{i}/{len(ingredients)}] {name[:40]}: Updated")
                else:
                    stats['errors'] += 1
                    print(f"  [{i}/{len(ingredients)}] {name[:40]}: Update failed")
            else:
                stats['not_found'] += 1
                if stats['not_found'] <= 20:
                    print(f"  [{i}/{len(ingredients)}] {name[:40]}: Not found in PubChem")

            if i % 50 == 0:
                print(f"\n  --- Progress: {i}/{len(ingredients)} | Updated: {stats['updated']} ---\n")

        print(f"\n{'='*50}")
        print("SUMMARY")
        print(f"{'='*50}")
        print(f"Ingredients processed: {len(ingredients)}")
        print(f"Found in PubChem: {stats['found']}")
        print(f"Successfully updated: {stats['updated']}")
        print(f"Not found in PubChem: {stats['not_found']}")
        print(f"Update errors: {stats['errors']}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Fetch PubChem data for ingredient drawers')
    parser.add_argument('--limit', type=int, help='Limit number of ingredients')
    parser.add_argument('--all', action='store_true', help='Process all ingredients')

    args = parser.parse_args()

    limit = None
    if args.limit:
        limit = args.limit
    elif not args.all:
        limit = 50  # Default

    updater = PubChemDrawerUpdater()
    updater.run(limit=limit)
