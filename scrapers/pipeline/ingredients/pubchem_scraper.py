"""
PubChem (NIH) Scraper

Retrieves:
- Molecular formula
- Molecular weight
- Chemical structure (SMILES)
- Physical properties
- Pharmacology/uses
- CAS number
- Synonyms
"""

import re
import time
from typing import Dict, List, Optional
from datetime import datetime

try:
    import requests
except ImportError:
    print("Install: pip install requests")
    raise

from .database import IngredientDatabase


# PubChem REST API (PUG REST)
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"


class PubChemScraper:
    """Scrapes PubChem for chemical/molecular ingredient data."""

    def __init__(self, db: IngredientDatabase = None):
        self.db = db or IngredientDatabase()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'iHeartClean-Ingredient-DB/1.0',
            'Accept': 'application/json',
        })
        self._last_request = 0
        self._min_delay = 0.5  # PubChem allows faster requests

    def _rate_limit(self):
        """Enforce minimum delay between requests."""
        elapsed = time.time() - self._last_request
        if elapsed < self._min_delay:
            time.sleep(self._min_delay - elapsed)
        self._last_request = time.time()

    def search_by_name(self, name: str) -> Optional[int]:
        """
        Search PubChem by compound name.

        Returns CID (Compound ID) if found, None otherwise.
        """
        self._rate_limit()

        url = f"{PUBCHEM_BASE}/compound/name/{requests.utils.quote(name)}/cids/JSON"

        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            cids = data.get('IdentifierList', {}).get('CID', [])
            return cids[0] if cids else None
        except requests.RequestException as e:
            print(f"PubChem search error: {e}")
            return None

    def search_by_cas(self, cas_number: str) -> Optional[int]:
        """
        Search PubChem by CAS registry number.

        Returns CID if found.
        """
        self._rate_limit()

        # Search in synonyms for CAS number
        url = f"{PUBCHEM_BASE}/compound/name/{cas_number}/cids/JSON"

        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            cids = data.get('IdentifierList', {}).get('CID', [])
            return cids[0] if cids else None
        except requests.RequestException:
            return None

    def get_compound_properties(self, cid: int) -> Optional[Dict]:
        """
        Get compound properties from PubChem.

        Returns dict with:
        - molecular_formula
        - molecular_weight
        - iupac_name
        - canonical_smiles
        - inchi
        """
        self._rate_limit()

        properties = [
            'MolecularFormula',
            'MolecularWeight',
            'IUPACName',
            'CanonicalSMILES',
            'InChI',
            'XLogP',
            'Complexity',
        ]

        url = f"{PUBCHEM_BASE}/compound/cid/{cid}/property/{','.join(properties)}/JSON"

        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            props = data.get('PropertyTable', {}).get('Properties', [{}])[0]

            return {
                'cid': cid,
                'molecular_formula': props.get('MolecularFormula'),
                'molecular_weight': props.get('MolecularWeight'),
                'iupac_name': props.get('IUPACName'),
                'canonical_smiles': props.get('CanonicalSMILES'),
                'inchi': props.get('InChI'),
                'xlogp': props.get('XLogP'),
                'complexity': props.get('Complexity'),
            }
        except requests.RequestException as e:
            print(f"PubChem properties error: {e}")
            return None

    def get_compound_synonyms(self, cid: int, limit: int = 20) -> List[str]:
        """Get compound synonyms/alternative names."""
        self._rate_limit()

        url = f"{PUBCHEM_BASE}/compound/cid/{cid}/synonyms/JSON"

        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            synonyms = data.get('InformationList', {}).get('Information', [{}])[0].get('Synonym', [])
            return synonyms[:limit]
        except requests.RequestException:
            return []

    def get_compound_description(self, cid: int) -> Optional[str]:
        """Get compound description from PubChem."""
        self._rate_limit()

        url = f"{PUBCHEM_VIEW}/data/compound/{cid}/JSON"

        try:
            resp = self.session.get(url, timeout=30, params={'heading': 'Record Description'})
            resp.raise_for_status()
            data = resp.json()

            # Navigate the nested structure to find description
            record = data.get('Record', {})
            sections = record.get('Section', [])

            for section in sections:
                if section.get('TOCHeading') == 'Record Description':
                    info = section.get('Information', [])
                    for item in info:
                        value = item.get('Value', {}).get('StringWithMarkup', [{}])
                        if value:
                            return value[0].get('String', '')
            return None
        except requests.RequestException:
            return None

    def get_pharmacology(self, cid: int) -> Optional[Dict]:
        """
        Get pharmacology/drug information for a compound.

        Returns info on uses, mechanism, absorption, etc.
        """
        self._rate_limit()

        url = f"{PUBCHEM_VIEW}/data/compound/{cid}/JSON"

        try:
            resp = self.session.get(url, timeout=30, params={'heading': 'Pharmacology and Biochemistry'})
            resp.raise_for_status()
            data = resp.json()

            pharmacology = {
                'uses': [],
                'mechanism': None,
                'absorption': None,
                'metabolism': None,
            }

            record = data.get('Record', {})
            sections = record.get('Section', [])

            for section in sections:
                heading = section.get('TOCHeading', '')

                if heading == 'Pharmacology and Biochemistry':
                    subsections = section.get('Section', [])
                    for sub in subsections:
                        sub_heading = sub.get('TOCHeading', '')
                        info = sub.get('Information', [])

                        if 'Use' in sub_heading:
                            for item in info:
                                val = item.get('Value', {}).get('StringWithMarkup', [{}])
                                if val:
                                    pharmacology['uses'].append(val[0].get('String', ''))

                        elif 'Mechanism' in sub_heading:
                            for item in info:
                                val = item.get('Value', {}).get('StringWithMarkup', [{}])
                                if val:
                                    pharmacology['mechanism'] = val[0].get('String', '')
                                    break

            return pharmacology if any(pharmacology.values()) else None
        except requests.RequestException:
            return None

    def get_physical_properties(self, cid: int) -> Optional[Dict]:
        """Get physical properties like melting point, solubility, etc."""
        self._rate_limit()

        url = f"{PUBCHEM_VIEW}/data/compound/{cid}/JSON"

        try:
            resp = self.session.get(url, timeout=30, params={'heading': 'Chemical and Physical Properties'})
            resp.raise_for_status()
            data = resp.json()

            properties = {
                'melting_point': None,
                'boiling_point': None,
                'solubility': None,
                'density': None,
                'color': None,
                'odor': None,
                'form': None,
            }

            record = data.get('Record', {})
            sections = record.get('Section', [])

            for section in sections:
                if section.get('TOCHeading') == 'Chemical and Physical Properties':
                    subsections = section.get('Section', [])
                    for sub in subsections:
                        sub_heading = sub.get('TOCHeading', '').lower()
                        info = sub.get('Information', [])

                        for item in info:
                            name = item.get('Name', '').lower()
                            val = item.get('Value', {})
                            string_val = val.get('StringWithMarkup', [{}])
                            num_val = val.get('Number', [])

                            text = string_val[0].get('String', '') if string_val else ''
                            if num_val:
                                text = str(num_val[0])

                            if 'melting' in name:
                                properties['melting_point'] = text
                            elif 'boiling' in name:
                                properties['boiling_point'] = text
                            elif 'solubil' in name:
                                properties['solubility'] = text
                            elif 'density' in name:
                                properties['density'] = text
                            elif 'color' in name:
                                properties['color'] = text
                            elif 'odor' in name or 'smell' in name:
                                properties['odor'] = text
                            elif 'form' in name or 'state' in name:
                                properties['form'] = text

            return properties if any(properties.values()) else None
        except requests.RequestException:
            return None

    def get_full_compound_data(self, name: str, cas_number: str = None) -> Optional[Dict]:
        """
        Get comprehensive compound data from PubChem.

        Searches by name (or CAS if provided) and retrieves all available data.
        """
        # Search for CID
        cid = None
        if cas_number:
            cid = self.search_by_cas(cas_number)
        if not cid:
            cid = self.search_by_name(name)

        if not cid:
            return None

        # Get all data
        compound_data = {
            'pubchem_cid': cid,
            'pubchem_url': f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
        }

        # Basic properties
        properties = self.get_compound_properties(cid)
        if properties:
            compound_data.update(properties)

        # Synonyms (for "Also Known As" field)
        synonyms = self.get_compound_synonyms(cid)
        if synonyms:
            compound_data['synonyms'] = synonyms

        # Description
        description = self.get_compound_description(cid)
        if description:
            compound_data['description'] = description

        # Physical properties (for Form, Scent fields)
        physical = self.get_physical_properties(cid)
        if physical:
            compound_data['physical_properties'] = physical
            if physical.get('odor'):
                compound_data['scent'] = physical['odor']
            if physical.get('form'):
                compound_data['form'] = physical['form']

        # Pharmacology (for Medicine field)
        pharmacology = self.get_pharmacology(cid)
        if pharmacology:
            compound_data['pharmacology'] = pharmacology
            if pharmacology.get('uses'):
                compound_data['medicinal_uses'] = '; '.join(pharmacology['uses'][:5])

        return compound_data

    def lookup_and_update(self, ingredient_name: str, cas_number: str = None) -> Optional[Dict]:
        """
        Look up ingredient in PubChem and update local database.

        Returns the PubChem data found.
        """
        data = self.get_full_compound_data(ingredient_name, cas_number)

        if not data:
            return None

        # Update database
        self._update_database(ingredient_name, data)

        return data

    def _update_database(self, ingredient_name: str, pubchem_data: Dict):
        """Update ingredient in database with PubChem data."""
        existing = self.db.get_by_name(ingredient_name)

        if existing:
            update_data = {}

            if pubchem_data.get('molecular_formula'):
                update_data['molecular_formula'] = pubchem_data['molecular_formula']
            if pubchem_data.get('molecular_weight'):
                update_data['molecular_weight'] = pubchem_data['molecular_weight']
            if pubchem_data.get('pubchem_cid'):
                update_data['pubchem_cid'] = pubchem_data['pubchem_cid']
            if pubchem_data.get('description') and not existing.description:
                update_data['description'] = pubchem_data['description'][:1000]
            if pubchem_data.get('synonyms') and not existing.common_names:
                # Add synonyms that aren't already in common names
                new_synonyms = [s for s in pubchem_data['synonyms'][:10]
                               if s.lower() != ingredient_name.lower()]
                if new_synonyms:
                    update_data['common_names'] = ','.join(new_synonyms)
            if pubchem_data.get('scent'):
                update_data['scent'] = pubchem_data['scent']
            if pubchem_data.get('medicinal_uses'):
                update_data['medicinal_uses'] = pubchem_data['medicinal_uses']

            if update_data:
                self.db.update_ingredient(ingredient_name, update_data)
                print(f"Updated {ingredient_name} with PubChem data")
        else:
            # Only create new entry if we have meaningful data
            from .models import IngredientData
            ingredient = IngredientData(
                inci_name=ingredient_name,
                molecular_formula=pubchem_data.get('molecular_formula'),
                molecular_weight=pubchem_data.get('molecular_weight'),
                pubchem_cid=pubchem_data.get('pubchem_cid'),
                description=pubchem_data.get('description', '')[:1000] if pubchem_data.get('description') else None,
                common_names=pubchem_data.get('synonyms', [])[:10],
            )
            self.db.add_ingredient(ingredient)
            print(f"Added {ingredient_name} from PubChem")


def enrich_ingredients_from_pubchem(db: IngredientDatabase, limit: int = 100) -> Dict:
    """
    Enrich existing ingredients with PubChem data.

    Prioritizes ingredients that have CAS numbers but missing chemistry data.
    """
    scraper = PubChemScraper(db)

    # Get ingredients that need enrichment
    ingredients = db.get_all(limit=limit)

    stats = {
        'total': 0,
        'enriched': 0,
        'not_found': 0,
        'errors': 0,
    }

    for ing in ingredients:
        # Skip if already has PubChem data
        if hasattr(ing, 'pubchem_cid') and ing.pubchem_cid:
            continue

        stats['total'] += 1

        try:
            result = scraper.lookup_and_update(ing.inci_name, getattr(ing, 'cas_number', None))
            if result:
                stats['enriched'] += 1
            else:
                stats['not_found'] += 1
        except Exception as e:
            print(f"Error enriching {ing.inci_name}: {e}")
            stats['errors'] += 1

    return stats


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        name = ' '.join(sys.argv[1:])
        print(f"Searching PubChem for: {name}\n")

        scraper = PubChemScraper()
        data = scraper.get_full_compound_data(name)

        if data:
            print(f"PubChem CID: {data.get('pubchem_cid')}")
            print(f"URL: {data.get('pubchem_url')}")
            print()

            if data.get('molecular_formula'):
                print(f"Formula: {data.get('molecular_formula')}")
            if data.get('molecular_weight'):
                print(f"MW: {data.get('molecular_weight')}")
            if data.get('iupac_name'):
                print(f"IUPAC: {data.get('iupac_name')}")

            if data.get('synonyms'):
                print(f"\nSynonyms: {', '.join(data['synonyms'][:5])}")

            if data.get('description'):
                print(f"\nDescription: {data['description'][:300]}...")

            if data.get('physical_properties'):
                print(f"\nPhysical Properties:")
                for k, v in data['physical_properties'].items():
                    if v:
                        print(f"  {k}: {v}")

            if data.get('medicinal_uses'):
                print(f"\nMedicinal Uses: {data['medicinal_uses'][:200]}...")
        else:
            print("Not found in PubChem")
    else:
        print("Usage: python -m ingredients.pubchem_scraper <ingredient name>")
