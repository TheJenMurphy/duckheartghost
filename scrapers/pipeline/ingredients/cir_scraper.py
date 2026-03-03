"""
CIR (Cosmetic Ingredient Review) Database Scraper

Scrapes ingredient safety data from https://cir-reports.cir-safety.org/

Updated January 2026 to work with new Power Apps Portal API structure.
"""

import re
import time
import requests
from typing import Optional, List, Dict, Generator
from datetime import datetime
from urllib.parse import urlencode

from .models import IngredientData
from .database import IngredientDatabase


# Rate limiting
REQUEST_DELAY = 0.5  # seconds between requests
USER_AGENT = 'iHeartClean-IngredientScraper/1.0 (cosmetic safety research)'

# CIR API endpoints
CIR_BASE_URL = 'https://cir-reports.cir-safety.org'
CIR_API_URL = f'{CIR_BASE_URL}/FetchCIRReports'

# CIR Safety conclusions extracted from report names
SAFETY_PATTERNS = [
    (r'unsafe', 'Unsafe'),
    (r'insufficient\s+data', 'Insufficient data'),
    (r'data\s+(?:are\s+)?insufficient', 'Insufficient data'),
    (r'safe\s+(?:as\s+used\s+)?with\s+qualification', 'Safe with qualifications'),
    (r'safe\s+when\s+formulated', 'Safe with qualifications'),
    (r'safe\s+(?:as\s+)?(?:currently\s+)?used', 'Safe as used'),
    (r'safe\s+for\s+use', 'Safe as used'),
    (r'safe\s+in\s+(?:the\s+)?(?:present\s+)?practices', 'Safe as used'),
    (r'safety\s+assessment', None),  # Just a report, need to look deeper
]


class CIRScraper:
    """Scrapes ingredient safety data from CIR database."""

    def __init__(self, db: IngredientDatabase = None):
        self.db = db or IngredientDatabase()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/json, text/javascript, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': CIR_BASE_URL,
        })
        self._last_request = 0
        self._all_records = []  # Cache for all CIR records

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self._last_request = time.time()

    def fetch_all_records(self, use_cache: bool = True) -> List[Dict]:
        """
        Fetch all CIR ingredient records.
        The API returns data in two parts and uses pagination.
        """
        if use_cache and self._all_records:
            return self._all_records

        all_records = []

        # Fetch part 1 (and its pages)
        records_part1 = self._fetch_with_pagination('')
        all_records.extend(records_part1)
        print(f"  Part 1: {len(records_part1)} records")

        # Fetch part 2 (and its pages)
        records_part2 = self._fetch_with_pagination('part2=true')
        all_records.extend(records_part2)
        print(f"  Part 2: {len(records_part2)} records")

        # Deduplicate by ingredient ID
        seen = set()
        unique_records = []
        for record in all_records:
            ing_id = record.get('pcpc_ingredientid', '')
            if ing_id and ing_id not in seen:
                seen.add(ing_id)
                unique_records.append(record)

        self._all_records = unique_records
        print(f"  Total unique: {len(unique_records)} records")
        return unique_records

    def _fetch_with_pagination(self, query_string: str) -> List[Dict]:
        """Fetch all pages for a given query string."""
        records = []
        page = 1
        paging_cookie = None

        while True:
            self._rate_limit()

            # Build URL with pagination
            params = query_string
            if paging_cookie:
                params += f"&pagingcookie={paging_cookie}&page={page}"

            url = f"{CIR_API_URL}?{params}" if params else CIR_API_URL

            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                print(f"Error fetching page {page}: {e}")
                break
            except ValueError as e:
                print(f"Error parsing JSON page {page}: {e}")
                break

            results = data.get('results', [])
            records.extend(results)

            # Check for more pages
            if data.get('morerecords') and results:
                paging_cookie = data.get('pagingcookie', '')
                page += 1
            else:
                break

        return records

    def fetch_all_by_letter(self, letter: str) -> Generator[Dict, None, None]:
        """
        Generator that yields ingredients starting with a specific letter.
        Fetches all data first, then filters by letter.
        """
        all_records = self.fetch_all_records()
        letter = letter.upper()

        for record in all_records:
            name = record.get('pcpc_ingredientname', '')
            if not name:
                continue

            first_char = name[0].upper()

            # Handle special cases
            if letter == '#':
                # Numbers and special characters
                if first_char.isdigit() or not first_char.isalnum():
                    yield record
            elif first_char == letter:
                yield record

    def parse_ingredient_record(self, record: Dict) -> Optional[IngredientData]:
        """
        Parse a CIR API record into IngredientData.
        Merges with existing data if present.
        """
        # Extract INCI name
        inci_name = (
            record.get('pcpc_ingredientname') or
            record.get('pcpc_ciringredientname') or
            record.get('pcpc_details_name')
        )

        if not inci_name:
            return None

        inci_name = inci_name.strip()

        # Check for existing ingredient
        existing = self.db.get_by_name(inci_name)
        if existing:
            ingredient = existing
        else:
            ingredient = IngredientData(inci_name=inci_name)

        # Extract CIR-specific data
        ingredient.cir_id = record.get('pcpc_ciringredientid') or record.get('pcpc_ingredientid')

        # Parse safety determination
        safety = self._extract_safety_determination(record)
        if safety:
            ingredient.cir_safety = safety['determination']
            ingredient.cir_conditions = safety.get('conditions')

        # Extract report URL
        report_id = record.get('pcpc_cirreportname') or record.get('_pcpc_cirreportid_value')
        if report_id:
            ingredient.cir_url = f'{CIR_BASE_URL}/view-attachment/?id={report_id}'

        # Extract year if available
        year = record.get('pcpc_publicationyear') or record.get('year')
        if year:
            try:
                ingredient.cir_year = int(year)
            except (ValueError, TypeError):
                pass

        # Extract function if available
        function = record.get('pcpc_function') or record.get('function')
        if function and not ingredient.function:
            ingredient.function = function

        # Set timestamp
        ingredient.cir_scraped_at = datetime.now()

        # Recompute flags
        ingredient._compute_flags()

        return ingredient

    def _extract_safety_determination(self, record: Dict) -> Optional[Dict]:
        """
        Extract safety determination from record.
        Returns dict with 'determination' and optional 'conditions'.

        The new CIR API only provides report names, so we extract
        safety conclusions from those.
        """
        # First check direct safety fields (if available)
        safety_fields = [
            'pcpc_safetydetermination',
            'safety_determination',
            'pcpc_conclusion',
            'conclusion',
            'pcpc_safetystatus',
        ]

        determination = None
        for field in safety_fields:
            value = record.get(field)
            if value:
                determination = str(value).strip()
                break

        # If no direct field, extract from report name
        if not determination:
            report_name = record.get('pcpc_cirreportname', '')
            if report_name:
                determination = self._parse_determination_from_report_name(report_name)

        # Try abstract/description as fallback
        if not determination:
            text_fields = ['pcpc_abstract', 'description', 'pcpc_summary']
            for field in text_fields:
                text = record.get(field, '')
                if text:
                    det = self._parse_determination_from_text(text)
                    if det:
                        determination = det
                        break

        if not determination:
            # If we have a report name, the ingredient has been reviewed
            # Default to "Reviewed" if we can't determine conclusion
            report_name = record.get('pcpc_cirreportname', '')
            if report_name:
                determination = 'Reviewed by CIR'
            else:
                return None

        # Normalize determination
        normalized = self._normalize_determination(determination)

        # Extract conditions if "safe with qualifications"
        conditions = None
        if 'qualification' in normalized.lower():
            conditions = self._extract_conditions(record)

        return {
            'determination': normalized,
            'conditions': conditions,
        }

    def _parse_determination_from_report_name(self, report_name: str) -> Optional[str]:
        """Extract safety determination from CIR report name."""
        report_lower = report_name.lower()

        for pattern, determination in SAFETY_PATTERNS:
            if re.search(pattern, report_lower):
                return determination

        # Check for Final Report (indicates completed review)
        if 'final report' in report_lower:
            return 'Safe as used'  # Final reports generally conclude safe

        # Check for amended safety assessment
        if 'amended' in report_lower:
            return 'Safe as used'  # Amended usually means reconfirmed safe

        return None

    def _normalize_determination(self, determination: str) -> str:
        """Normalize safety determination to standard values."""
        det_lower = determination.lower()

        if 'unsafe' in det_lower:
            return 'Unsafe'
        elif 'insufficient' in det_lower or 'data needed' in det_lower:
            return 'Insufficient data'
        elif 'safe with' in det_lower or 'qualification' in det_lower:
            return 'Safe with qualifications'
        elif 'safe' in det_lower:
            return 'Safe as used'
        else:
            return determination

    def _parse_determination_from_text(self, text: str) -> Optional[str]:
        """Parse safety determination from abstract/summary text."""
        patterns = [
            (r'(?:determined|concluded|found)\s+(?:to\s+be\s+)?unsafe', 'Unsafe'),
            (r'insufficient\s+data', 'Insufficient data'),
            (r'safe\s+(?:as\s+used\s+)?with\s+qualification', 'Safe with qualifications'),
            (r'safe\s+as\s+(?:currently\s+)?used', 'Safe as used'),
            (r'safe\s+for\s+use', 'Safe as used'),
        ]

        text_lower = text.lower()
        for pattern, determination in patterns:
            if re.search(pattern, text_lower):
                return determination

        return None

    def _extract_conditions(self, record: Dict) -> Optional[str]:
        """Extract conditions/qualifications for safe with qualifications."""
        # Look for conditions in various fields
        condition_fields = [
            'pcpc_qualifications',
            'pcpc_conditions',
            'qualifications',
            'conditions',
        ]

        for field in condition_fields:
            value = record.get(field)
            if value:
                return str(value).strip()[:500]

        # Try to extract from abstract
        abstract = record.get('pcpc_abstract', '')
        if abstract:
            match = re.search(
                r'(?:when|provided|if)\s+([^.]{20,200})',
                abstract, re.IGNORECASE
            )
            if match:
                return match.group(1).strip()

        return None

    def scrape_and_save(self, record: Dict) -> Optional[IngredientData]:
        """
        Parse and save a CIR record to database.
        Returns the ingredient data or None if parsing failed.
        """
        ingredient = self.parse_ingredient_record(record)
        if ingredient:
            self.db.upsert(ingredient)
        return ingredient

    def scrape_letter(self, letter: str, progress_callback=None) -> int:
        """
        Scrape all ingredients for a letter.
        Returns count of ingredients scraped.
        """
        count = 0
        for record in self.fetch_all_by_letter(letter):
            ingredient = self.scrape_and_save(record)
            if ingredient:
                count += 1
                if progress_callback:
                    progress_callback(count, letter, ingredient.inci_name)
        return count

    def scrape_all(self, progress_callback=None) -> int:
        """
        Scrape entire CIR database.
        Fetches all records at once, then processes them.
        Returns total count of ingredients scraped.
        """
        print("Fetching all CIR records...")
        all_records = self.fetch_all_records(use_cache=False)

        total = 0
        matched = 0

        print(f"\nProcessing {len(all_records)} CIR records...")

        for i, record in enumerate(all_records):
            ingredient = self.scrape_and_save(record)
            if ingredient:
                total += 1
                # Check if this matched an existing ingredient in our DB
                if self.db.get_by_name(ingredient.inci_name):
                    matched += 1

                if progress_callback:
                    progress_callback(total, 'ALL', ingredient.inci_name)

                # Progress update every 500
                if total % 500 == 0:
                    print(f"  Processed {total} ingredients...")

        print(f"\nTotal CIR ingredients processed: {total}")
        print(f"Matched to existing DB entries: {matched}")

        return total

    def lookup_ingredient(self, name: str) -> Optional[IngredientData]:
        """
        Look up a specific ingredient in CIR database.
        First checks local cache, then searches CIR if not found.
        """
        # Check database first
        existing = self.db.lookup(name)
        if existing and existing.cir_safety:
            return existing

        # Search CIR by first letter
        first_letter = name[0].upper() if name else '#'
        if not first_letter.isalpha():
            first_letter = '#'

        name_lower = name.lower()
        for record in self.fetch_all_by_letter(first_letter):
            record_name = (
                record.get('pcpc_ingredientname') or
                record.get('pcpc_ciringredientname') or ''
            )
            if record_name.lower() == name_lower:
                return self.scrape_and_save(record)

        return None


def scrape_cir_database(db: IngredientDatabase = None, letters: str = None) -> Dict:
    """
    Scrape CIR database.

    Args:
        db: Database instance (creates default if None)
        letters: Specific letters to scrape (e.g., 'ABC') or None for all

    Returns:
        Dict with scraping statistics
    """
    db = db or IngredientDatabase()
    scraper = CIRScraper(db)

    start_time = time.time()
    stats = {
        'letters_scraped': [],
        'ingredients_found': 0,
        'errors': 0,
    }

    target_letters = list(letters.upper()) if letters else list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + ['#']

    def progress(count, letter, name):
        print(f"  [{letter}] {count}: {name}")

    for letter in target_letters:
        try:
            print(f"\n{'='*40}")
            print(f"Scraping letter: {letter}")
            print('='*40)

            count = scraper.scrape_letter(letter, progress_callback=progress)
            stats['letters_scraped'].append(letter)
            stats['ingredients_found'] += count

        except Exception as e:
            print(f"Error scraping letter {letter}: {e}")
            stats['errors'] += 1

    stats['duration_seconds'] = round(time.time() - start_time, 2)
    stats['database_stats'] = db.get_stats()

    return stats


if __name__ == '__main__':
    import sys

    db = IngredientDatabase()

    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg == '--full':
            # Full database scrape
            print("Scraping full CIR database...")
            stats = scrape_cir_database(db)
            print(f"\n{'='*40}")
            print("SCRAPE COMPLETE")
            print('='*40)
            print(f"Ingredients found: {stats['ingredients_found']}")
            print(f"Duration: {stats['duration_seconds']}s")
            print(f"Database stats: {stats['database_stats']}")

        elif len(arg) <= 3 and arg.isalpha():
            # Scrape specific letters
            print(f"Scraping letters: {arg.upper()}")
            stats = scrape_cir_database(db, letters=arg)
            print(f"\nIngredients found: {stats['ingredients_found']}")

        else:
            # Look up specific ingredient
            name = ' '.join(sys.argv[1:])
            print(f"Looking up: {name}")
            scraper = CIRScraper(db)
            ingredient = scraper.lookup_ingredient(name)
            if ingredient:
                print(f"  Name: {ingredient.inci_name}")
                print(f"  CIR Safety: {ingredient.cir_safety}")
                print(f"  Conditions: {ingredient.cir_conditions}")
                print(f"  Year: {ingredient.cir_year}")
            else:
                print("  Not found in CIR database")

    else:
        print("Usage:")
        print("  python cir_scraper.py --full           # Scrape entire database")
        print("  python cir_scraper.py ABC              # Scrape letters A, B, C")
        print("  python cir_scraper.py 'Glycerin'       # Look up specific ingredient")
