"""
CosIng (European Commission Cosmetic Ingredient Database) Scraper

Updated January 2026 to use CSV bulk data instead of web scraping.
The EU CosIng website changed structure, so we now download the full
ingredient inventory CSV and search locally.

Retrieves:
- Official INCI names
- CAS numbers
- EC/EINECS numbers
- Cosmetic functions
- Chemical descriptions
- Regulatory restrictions
"""

import csv
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

try:
    import requests
except ImportError:
    print("Install: pip install requests")
    raise

from .database import IngredientDatabase


# CosIng CSV data source (via Wayback Machine archive)
COSING_CSV_URL = "https://web.archive.org/web/20220926233955mp_/https://ec.europa.eu/growth/tools-databases/cosing/pdf/COSING_Ingredients-Fragrance%20Inventory_v2.csv"

# Local cache location
CACHE_DIR = Path(__file__).parent.parent / "data"
COSING_CACHE_FILE = CACHE_DIR / "cosing_ingredients.csv"


class CosIngScraper:
    """
    Searches the EU CosIng database for ingredient identifiers and regulatory data.

    Uses a downloaded CSV file for fast local searching instead of web scraping.
    """

    def __init__(self, db: IngredientDatabase = None):
        self.db = db or IngredientDatabase()
        self._ingredients: List[Dict] = []
        self._inci_index: Dict[str, Dict] = {}  # lowercase INCI name -> record
        self._cas_index: Dict[str, Dict] = {}   # CAS number -> record
        self._loaded = False

    def _ensure_data_loaded(self):
        """Load CosIng data if not already loaded."""
        if self._loaded:
            return

        # Try to load from cache first
        if COSING_CACHE_FILE.exists():
            self._load_from_csv(COSING_CACHE_FILE)
        else:
            # Download and cache
            self._download_and_cache()
            self._load_from_csv(COSING_CACHE_FILE)

        self._loaded = True

    def _download_and_cache(self):
        """Download CosIng CSV and cache locally."""
        print("Downloading CosIng ingredient database...")

        try:
            resp = requests.get(COSING_CSV_URL, timeout=60)
            resp.raise_for_status()

            # Ensure cache directory exists
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # Save to cache
            with open(COSING_CACHE_FILE, 'wb') as f:
                f.write(resp.content)

            print(f"  Cached to {COSING_CACHE_FILE}")

        except requests.RequestException as e:
            print(f"Error downloading CosIng data: {e}")
            raise

    def _load_from_csv(self, filepath: Path):
        """Load and index CosIng data from CSV file."""
        print(f"Loading CosIng data from {filepath}...")

        self._ingredients = []
        self._inci_index = {}
        self._cas_index = {}

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            # Skip metadata lines until we find the header
            for line in f:
                if line.startswith('COSING Ref No'):
                    # Found header, create reader from here
                    # Put header back and read rest
                    remaining = line + f.read()
                    break
            else:
                print("  Could not find header row")
                return

        # Parse CSV
        reader = csv.DictReader(remaining.splitlines())

        for row in reader:
            # Clean up the row data
            record = {
                'cosing_id': row.get('COSING Ref No', '').strip(),
                'inci_name': row.get('INCI name', '').strip(),
                'inn_name': row.get('INN name', '').strip(),
                'ph_eur_name': row.get('Ph. Eur. Name', '').strip(),
                'cas_number': self._clean_cas(row.get('CAS No', '')),
                'ec_number': self._clean_ec(row.get('EC No', '')),
                'description': row.get('Chem/IUPAC Name / Description', '').strip(),
                'restriction': row.get('Restriction', '').strip(),
                'functions': self._parse_functions(row.get('Function', '')),
                'update_date': row.get('Update Date', '').strip(),
            }

            # Skip empty records
            if not record['inci_name']:
                continue

            self._ingredients.append(record)

            # Index by INCI name (lowercase for case-insensitive search)
            inci_lower = record['inci_name'].lower().strip()
            self._inci_index[inci_lower] = record

            # Index by CAS number if present
            if record['cas_number']:
                # Handle multiple CAS numbers
                for cas in record['cas_number'].split(','):
                    cas = cas.strip()
                    if cas:
                        self._cas_index[cas] = record

        print(f"  Loaded {len(self._ingredients)} ingredients")
        print(f"  Indexed {len(self._inci_index)} INCI names")
        print(f"  Indexed {len(self._cas_index)} CAS numbers")

    def _clean_cas(self, cas: str) -> Optional[str]:
        """Clean and validate CAS number(s)."""
        if not cas:
            return None

        cas = cas.strip()
        if not cas or cas == ' ':
            return None

        # Extract all CAS numbers (format: XXXXXXX-XX-X)
        cas_numbers = re.findall(r'\d{2,7}-\d{2}-\d', cas)

        if cas_numbers:
            return ', '.join(cas_numbers)
        return None

    def _clean_ec(self, ec: str) -> Optional[str]:
        """Clean and validate EC number."""
        if not ec:
            return None

        ec = ec.strip()
        if not ec or ec == ' ':
            return None

        # EC format: XXX-XXX-X
        match = re.search(r'(\d{3}-\d{3}-\d)', ec)
        return match.group(1) if match else None

    def _parse_functions(self, func_str: str) -> List[str]:
        """Parse comma-separated function list."""
        if not func_str:
            return []

        functions = []
        for f in func_str.split(','):
            f = f.strip()
            if f:
                # Normalize function names
                f = f.title().replace('_', ' ')
                functions.append(f)

        return functions

    def search_ingredient(self, name: str) -> List[Dict]:
        """
        Search CosIng for an ingredient by name.

        Returns list of matches with:
        - inci_name: Official INCI name
        - cas_number: CAS registry number
        - ec_number: EC/EINECS number
        - functions: List of cosmetic functions
        - cosing_id: Internal CosIng reference ID
        - description: Chemical/IUPAC description
        - restriction: Any regulatory restrictions
        """
        self._ensure_data_loaded()

        name_lower = name.lower().strip()
        results = []

        # Exact match first
        if name_lower in self._inci_index:
            results.append(self._inci_index[name_lower])

        # If no exact match, search for partial matches
        if not results:
            for inci_lower, record in self._inci_index.items():
                # Check if search term is contained in INCI name
                if name_lower in inci_lower:
                    results.append(record)
                # Check if INCI name starts with search term
                elif inci_lower.startswith(name_lower):
                    results.append(record)
                # Check word-by-word match
                elif any(word.startswith(name_lower) for word in inci_lower.split()):
                    results.append(record)

                # Limit results
                if len(results) >= 20:
                    break

        return results

    def search_by_cas(self, cas_number: str) -> Optional[Dict]:
        """Search CosIng by CAS registry number."""
        self._ensure_data_loaded()

        cas = cas_number.strip()
        return self._cas_index.get(cas)

    def get_ingredient(self, inci_name: str) -> Optional[Dict]:
        """Get exact match for an INCI name."""
        self._ensure_data_loaded()

        return self._inci_index.get(inci_name.lower().strip())

    def lookup_and_update(self, ingredient_name: str) -> Optional[Dict]:
        """
        Search CosIng for an ingredient and update the local database.

        Returns the CosIng data found, or None if not found.
        """
        results = self.search_ingredient(ingredient_name)

        if not results:
            return None

        # Find best match
        best_match = self._find_best_match(results, ingredient_name)
        if not best_match:
            return None

        # Update database
        self._update_database(ingredient_name, best_match)

        return best_match

    def _find_best_match(self, results: List[Dict], search_term: str) -> Optional[Dict]:
        """Find the best matching result for a search term."""
        if not results:
            return None

        search_lower = search_term.lower().strip()

        # Score each result
        scored = []
        for result in results:
            inci_name = result.get('inci_name', '').lower()
            score = 0

            # Exact match
            if inci_name == search_lower:
                score = 100
            # Starts with
            elif inci_name.startswith(search_lower):
                score = 80
            # Contains
            elif search_lower in inci_name:
                score = 60
            # Partial word match
            else:
                words = search_lower.split()
                matches = sum(1 for w in words if w in inci_name)
                score = 30 * (matches / len(words)) if words else 0

            # Boost if has CAS number (more reliable data)
            if result.get('cas_number'):
                score += 10

            scored.append((score, result))

        # Return highest scoring result above threshold
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored and scored[0][0] >= 30:
            return scored[0][1]
        return results[0] if results else None

    def _update_database(self, ingredient_name: str, cosing_data: Dict):
        """Update ingredient in database with CosIng data."""
        existing = self.db.get_by_name(ingredient_name)

        if existing:
            # Update existing record with CosIng data
            update_data = {}

            if cosing_data.get('cas_number') and not getattr(existing, 'cas_number', None):
                update_data['cas_number'] = cosing_data['cas_number']

            if cosing_data.get('ec_number') and not getattr(existing, 'ec_number', None):
                update_data['ec_number'] = cosing_data['ec_number']

            if cosing_data.get('functions') and not getattr(existing, 'function', None):
                update_data['function'] = ', '.join(cosing_data['functions'])

            if cosing_data.get('description') and not getattr(existing, 'description', None):
                # Truncate long descriptions
                desc = cosing_data['description'][:500]
                update_data['description'] = desc

            # Note: eu_restriction field may not exist in database schema
            # if cosing_data.get('restriction'):
            #     update_data['eu_restriction'] = cosing_data['restriction']

            if update_data:
                self.db.update_ingredient(ingredient_name, update_data)
                print(f"Updated {ingredient_name} with CosIng data")
        else:
            # Create new ingredient with CosIng data
            from .models import IngredientData
            ingredient = IngredientData(
                inci_name=cosing_data.get('inci_name', ingredient_name),
                cas_number=cosing_data.get('cas_number'),
                ec_number=cosing_data.get('ec_number'),
                function=', '.join(cosing_data.get('functions', [])),
                description=cosing_data.get('description', '')[:500] if cosing_data.get('description') else None,
            )
            self.db.add_ingredient(ingredient)
            print(f"Added {ingredient_name} from CosIng")

    def get_all_ingredients(self) -> List[Dict]:
        """Get all CosIng ingredients."""
        self._ensure_data_loaded()
        return self._ingredients

    def refresh_cache(self):
        """Force re-download of CosIng data."""
        if COSING_CACHE_FILE.exists():
            COSING_CACHE_FILE.unlink()
        self._loaded = False
        self._ensure_data_loaded()


def scrape_cosing_batch(db: IngredientDatabase, ingredient_names: List[str]) -> Dict:
    """
    Batch lookup CosIng data for multiple ingredients.

    Returns statistics on the operation.
    """
    scraper = CosIngScraper(db)

    stats = {
        'total': len(ingredient_names),
        'found': 0,
        'not_found': 0,
        'errors': 0,
    }

    for name in ingredient_names:
        try:
            result = scraper.lookup_and_update(name)
            if result:
                stats['found'] += 1
            else:
                stats['not_found'] += 1
        except Exception as e:
            print(f"Error looking up {name}: {e}")
            stats['errors'] += 1

    return stats


def enrich_from_cosing(db: IngredientDatabase = None, limit: int = None) -> Dict:
    """
    Enrich existing database ingredients with CosIng data.

    Args:
        db: Database instance
        limit: Maximum number of ingredients to process

    Returns:
        Statistics dict
    """
    db = db or IngredientDatabase()
    scraper = CosIngScraper(db)

    # Get all ingredients from database
    ingredients = db.get_all(limit=limit)

    stats = {
        'total': len(ingredients),
        'enriched': 0,
        'not_found': 0,
        'already_has_data': 0,
    }

    print(f"Enriching {len(ingredients)} ingredients from CosIng...")

    for i, ing in enumerate(ingredients):
        # Skip if already has CAS number (likely already enriched from CosIng)
        if hasattr(ing, 'cas_number') and ing.cas_number:
            stats['already_has_data'] += 1
            continue

        result = scraper.lookup_and_update(ing.inci_name)
        if result:
            stats['enriched'] += 1
        else:
            stats['not_found'] += 1

        # Progress update
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(ingredients)}...")

    print(f"\nCosIng enrichment complete:")
    print(f"  Enriched: {stats['enriched']}")
    print(f"  Not found: {stats['not_found']}")
    print(f"  Already had data: {stats['already_has_data']}")

    return stats


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == '--refresh':
            # Force refresh of cached data
            print("Refreshing CosIng cache...")
            scraper = CosIngScraper()
            scraper.refresh_cache()
            print("Done!")

        elif sys.argv[1] == '--enrich':
            # Enrich database from CosIng
            from .database import IngredientDatabase
            db = IngredientDatabase()
            stats = enrich_from_cosing(db)
            print(f"\nDatabase stats: {db.get_stats()}")

        elif sys.argv[1] == '--stats':
            # Show CosIng data stats
            scraper = CosIngScraper()
            scraper._ensure_data_loaded()
            print(f"Total ingredients: {len(scraper._ingredients)}")
            print(f"With CAS numbers: {len(scraper._cas_index)}")

            # Count by function
            functions = {}
            for ing in scraper._ingredients:
                for func in ing.get('functions', []):
                    functions[func] = functions.get(func, 0) + 1

            print(f"\nTop 10 functions:")
            for func, count in sorted(functions.items(), key=lambda x: -x[1])[:10]:
                print(f"  {func}: {count}")
        else:
            # Search for ingredient
            name = ' '.join(sys.argv[1:])
            print(f"Searching CosIng for: {name}\n")

            scraper = CosIngScraper()
            results = scraper.search_ingredient(name)

            if results:
                print(f"Found {len(results)} result(s):\n")
                for i, r in enumerate(results[:5], 1):
                    print(f"{i}. {r.get('inci_name')}")
                    if r.get('cas_number'):
                        print(f"   CAS#: {r.get('cas_number')}")
                    if r.get('ec_number'):
                        print(f"   EC#: {r.get('ec_number')}")
                    if r.get('functions'):
                        print(f"   Functions: {', '.join(r.get('functions'))}")
                    if r.get('restriction'):
                        print(f"   Restriction: {r.get('restriction')[:100]}...")
                    print()
            else:
                print("No results found")
    else:
        print("CosIng Ingredient Database Lookup")
        print()
        print("Usage:")
        print("  python -m ingredients.cosing_scraper <ingredient name>  # Search for ingredient")
        print("  python -m ingredients.cosing_scraper --refresh          # Refresh cached data")
        print("  python -m ingredients.cosing_scraper --enrich           # Enrich database")
        print("  python -m ingredients.cosing_scraper --stats            # Show data statistics")
