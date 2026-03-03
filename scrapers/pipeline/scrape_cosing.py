#!/usr/bin/env python3
"""
Scrape CosIng (EU Cosmetic Ingredients Database) for ingredient data.

CosIng is the EU's official cosmetic ingredient database - no login required!

Usage:
    python scrape_cosing.py --mystery     # Scrape mystery ingredients only
    python scrape_cosing.py --limit 50    # Scrape first 50 mystery ingredients
    python scrape_cosing.py --ingredient "Dimethicone"  # Single ingredient
"""

import os
import sys
import time
import csv
import re
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

import requests
from bs4 import BeautifulSoup
import functools
print = functools.partial(print, flush=True)

# CosIng API/URLs
COSING_SEARCH_URL = "https://ec.europa.eu/growth/tools-databases/cosing/index.cfm"
COSING_API_URL = "https://ec.europa.eu/growth/tools-databases/cosing/api/v1"

# Output files
OUTPUT_CSV = Path(__file__).parent / 'data' / 'cosing_ingredients.csv'
OUTPUT_JSON = Path(__file__).parent / 'data' / 'cosing_ingredients.json'
MYSTERY_CSV = Path(__file__).parent / 'data' / 'pubmed_ingredient_fulltext.csv'


class CosingScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/html',
        })

    def search_ingredient(self, ingredient_name: str) -> Optional[Dict]:
        """Search CosIng for an ingredient."""
        result = {
            'search_name': ingredient_name,
            'inci_name': '',
            'inn_name': '',
            'cas_number': '',
            'ec_number': '',
            'functions': [],
            'description': '',
            'restrictions': '',
            'sccs_opinions': [],
            'update_date': '',
        }

        try:
            # Try the API first
            api_result = self._search_api(ingredient_name)
            if api_result:
                return api_result

            # Fall back to web scraping
            web_result = self._search_web(ingredient_name)
            if web_result:
                return web_result

        except Exception as e:
            print(f"    Error: {e}")

        return None

    def _search_api(self, ingredient_name: str) -> Optional[Dict]:
        """Search using CosIng API."""
        try:
            # CosIng ingredient search endpoint
            params = {
                'q': ingredient_name,
            }

            resp = self.session.get(
                f"{COSING_API_URL}/ingredients",
                params=params,
                timeout=30
            )

            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list) and len(data) > 0:
                    ing = data[0]
                    return {
                        'search_name': ingredient_name,
                        'inci_name': ing.get('inci_name', ''),
                        'inn_name': ing.get('inn_name', ''),
                        'cas_number': ing.get('cas_no', ''),
                        'ec_number': ing.get('ec_no', ''),
                        'functions': ing.get('functions', []) if isinstance(ing.get('functions'), list) else [ing.get('functions', '')],
                        'description': ing.get('description', ''),
                        'restrictions': ing.get('restrictions', ''),
                        'sccs_opinions': ing.get('sccs_opinions', []),
                        'update_date': ing.get('update_date', ''),
                    }

        except Exception:
            pass

        return None

    def _search_web(self, ingredient_name: str) -> Optional[Dict]:
        """Search CosIng via web interface."""
        try:
            # Search page
            search_url = f"{COSING_SEARCH_URL}?fuession.action=search.simple&search.searchtext={quote_plus(ingredient_name)}"

            resp = self.session.get(search_url, timeout=30)

            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')

            result = {
                'search_name': ingredient_name,
                'inci_name': '',
                'inn_name': '',
                'cas_number': '',
                'ec_number': '',
                'functions': [],
                'description': '',
                'restrictions': '',
                'sccs_opinions': [],
                'update_date': '',
            }

            # Look for result table
            table = soup.find('table', class_=re.compile(r'result|data'))
            if table:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)

                        if 'inci' in label:
                            result['inci_name'] = value
                        elif 'cas' in label:
                            result['cas_number'] = value
                        elif 'ec' in label or 'einecs' in label:
                            result['ec_number'] = value
                        elif 'function' in label:
                            result['functions'] = [f.strip() for f in value.split(',')]
                        elif 'restriction' in label:
                            result['restrictions'] = value

            # Also look for ingredient detail links
            detail_links = soup.find_all('a', href=re.compile(r'details\.cfm\?id='))
            if detail_links:
                detail_url = detail_links[0].get('href')
                if not detail_url.startswith('http'):
                    detail_url = f"https://ec.europa.eu/growth/tools-databases/cosing/{detail_url}"

                detail_result = self._get_ingredient_details(detail_url)
                if detail_result:
                    # Merge results
                    for key, value in detail_result.items():
                        if value and not result.get(key):
                            result[key] = value

            if result['inci_name'] or result['cas_number'] or result['functions']:
                return result

        except Exception as e:
            pass

        return None

    def _get_ingredient_details(self, url: str) -> Optional[Dict]:
        """Get detailed ingredient information."""
        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')

            result = {
                'inci_name': '',
                'inn_name': '',
                'cas_number': '',
                'ec_number': '',
                'functions': [],
                'description': '',
                'restrictions': '',
                'sccs_opinions': [],
            }

            # Parse detail page
            for dl in soup.find_all(['dl', 'table']):
                text = dl.get_text(separator='|', strip=True)

                # Parse key-value pairs
                for pair in text.split('|'):
                    if ':' in pair:
                        key, value = pair.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip()

                        if 'inci' in key and 'name' in key:
                            result['inci_name'] = value
                        elif 'cas' in key:
                            result['cas_number'] = value
                        elif 'ec' in key:
                            result['ec_number'] = value
                        elif 'function' in key:
                            result['functions'] = [f.strip() for f in value.split(',')]
                        elif 'restriction' in key:
                            result['restrictions'] = value
                        elif 'description' in key:
                            result['description'] = value

            return result

        except Exception:
            return None


def get_mystery_ingredients(limit: Optional[int] = None) -> List[str]:
    """Get ingredients with no PubMed data."""
    mystery = []

    if not MYSTERY_CSV.exists():
        print(f"Mystery CSV not found: {MYSTERY_CSV}")
        return []

    with open(MYSTERY_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            results = int(row.get('pubmed_total_results', 0) or 0)
            benefits = row.get('skin_benefits', '')
            if results == 0 and not benefits:
                mystery.append(row['name'])

    if limit:
        mystery = mystery[:limit]

    return mystery


def main():
    print("=" * 70)
    print("COSING (EU COSMETIC INGREDIENTS) SCRAPER")
    print("=" * 70)
    print()

    args = sys.argv[1:]

    # Parse arguments
    limit = None
    single_ingredient = None
    mystery_only = False

    for i, arg in enumerate(args):
        if arg == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1])
        elif arg == '--ingredient' and i + 1 < len(args):
            single_ingredient = args[i + 1]
        elif arg == '--mystery':
            mystery_only = True

    if not mystery_only and not single_ingredient and limit is None:
        print(__doc__)
        return

    # Initialize scraper
    scraper = CosingScraper()

    # Get ingredients to scrape
    if single_ingredient:
        ingredients = [single_ingredient]
    elif mystery_only or limit:
        ingredients = get_mystery_ingredients(limit)
        print(f"Found {len(ingredients)} mystery ingredients to look up")
    else:
        return

    if not ingredients:
        print("No ingredients to process")
        return

    # Prepare output
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        'search_name',
        'inci_name',
        'inn_name',
        'cas_number',
        'ec_number',
        'functions',
        'description',
        'restrictions',
        'sccs_opinions',
        'update_date',
        'scraped_date',
    ]

    all_data = []

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        print(f"\nSearching CosIng for {len(ingredients)} ingredients...")
        print()

        found = 0
        not_found = 0

        for i, ingredient in enumerate(ingredients, 1):
            print(f"[{i}/{len(ingredients)}] {ingredient[:40]}...", end=' ')

            result = scraper.search_ingredient(ingredient)
            time.sleep(0.5)  # Rate limiting

            if result and (result.get('inci_name') or result.get('functions')):
                found += 1
                funcs = result.get('functions', [])
                print(f"Found! Functions: {', '.join(funcs[:3]) if funcs else 'N/A'}")

                row = {
                    'search_name': ingredient,
                    'inci_name': result.get('inci_name', ''),
                    'inn_name': result.get('inn_name', ''),
                    'cas_number': result.get('cas_number', ''),
                    'ec_number': result.get('ec_number', ''),
                    'functions': '; '.join(result.get('functions', [])) if isinstance(result.get('functions'), list) else result.get('functions', ''),
                    'description': result.get('description', ''),
                    'restrictions': result.get('restrictions', ''),
                    'sccs_opinions': '; '.join(result.get('sccs_opinions', [])) if isinstance(result.get('sccs_opinions'), list) else '',
                    'update_date': result.get('update_date', ''),
                    'scraped_date': datetime.now().isoformat(),
                }

                writer.writerow(row)
                all_data.append(row)
            else:
                not_found += 1
                print("Not found")

    # Save JSON
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Ingredients searched: {len(ingredients)}")
    print(f"Found: {found}")
    print(f"Not found: {not_found}")
    print()
    print(f"CSV output: {OUTPUT_CSV}")
    print(f"JSON output: {OUTPUT_JSON}")


if __name__ == '__main__':
    main()
