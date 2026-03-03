#!/usr/bin/env python3
"""
Scrape UL Prospector for ingredient technical data.

Requires UL Prospector account credentials in .env:
    UL_PROSPECTOR_EMAIL=your_email
    UL_PROSPECTOR_PASSWORD=your_password

Usage:
    python scrape_ul_prospector.py --mystery     # Scrape mystery ingredients only
    python scrape_ul_prospector.py --limit 50   # Scrape first 50 mystery ingredients
    python scrape_ul_prospector.py --ingredient "Dimethicone"  # Single ingredient
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
from urllib.parse import urljoin, quote_plus

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

import requests
from bs4 import BeautifulSoup
import functools
print = functools.partial(print, flush=True)

# UL Prospector URLs
BASE_URL = "https://www.ulprospector.com"
LOGIN_URL = "https://www.ulprospector.com/en/na/PersonalCare/Account/Login"
SEARCH_URL = "https://www.ulprospector.com/en/na/PersonalCare/search"

# Output files
OUTPUT_CSV = Path(__file__).parent / 'data' / 'ul_prospector_ingredients.csv'
OUTPUT_JSON = Path(__file__).parent / 'data' / 'ul_prospector_ingredients.json'
MYSTERY_CSV = Path(__file__).parent / 'data' / 'pubmed_ingredient_fulltext.csv'


class ULProspectorScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.logged_in = False

    def login(self) -> bool:
        """Login to UL Prospector."""
        email = os.environ.get('UL_PROSPECTOR_EMAIL', '')
        password = os.environ.get('UL_PROSPECTOR_PASSWORD', '')

        if not email or not password:
            print("ERROR: UL_PROSPECTOR_EMAIL and UL_PROSPECTOR_PASSWORD must be set in .env")
            return False

        print(f"Logging in to UL Prospector as {email}...")

        try:
            # Get login page to get CSRF token
            resp = self.session.get(LOGIN_URL, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find the verification token
            token_input = soup.find('input', {'name': '__RequestVerificationToken'})
            token = token_input['value'] if token_input else ''

            # Login
            login_data = {
                'Email': email,
                'Password': password,
                '__RequestVerificationToken': token,
                'RememberMe': 'true',
            }

            resp = self.session.post(
                LOGIN_URL,
                data=login_data,
                timeout=30,
                allow_redirects=True
            )

            # Check if login was successful
            if 'logout' in resp.text.lower() or 'sign out' in resp.text.lower() or resp.url != LOGIN_URL:
                print("  Login successful!")
                self.logged_in = True
                return True
            else:
                print("  Login failed - check credentials")
                return False

        except Exception as e:
            print(f"  Login error: {e}")
            return False

    def search_ingredient(self, ingredient_name: str) -> List[Dict]:
        """Search for an ingredient and return matching products."""
        if not self.logged_in:
            return []

        results = []

        try:
            # Search URL
            search_params = {
                'k': ingredient_name,
                'searchType': 'INCI',
            }

            resp = self.session.get(
                SEARCH_URL,
                params=search_params,
                timeout=30
            )
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find search results
            result_items = soup.find_all('div', class_='search-result-item') or \
                          soup.find_all('tr', class_='product-row') or \
                          soup.find_all('div', class_='product-card')

            for item in result_items[:5]:  # Limit to first 5 results
                result = self._parse_search_result(item)
                if result:
                    results.append(result)

            # If no results found in standard format, try alternative parsing
            if not results:
                # Look for product links
                product_links = soup.find_all('a', href=re.compile(r'/Product/'))
                for link in product_links[:5]:
                    product_url = urljoin(BASE_URL, link.get('href', ''))
                    product_data = self.get_product_details(product_url)
                    if product_data:
                        results.append(product_data)
                    time.sleep(0.5)

        except Exception as e:
            print(f"    Search error: {e}")

        return results

    def _parse_search_result(self, item) -> Optional[Dict]:
        """Parse a search result item."""
        try:
            result = {
                'trade_name': '',
                'supplier': '',
                'inci_name': '',
                'functions': [],
                'description': '',
                'product_url': '',
            }

            # Trade name
            name_elem = item.find(['h3', 'h4', 'a'], class_=re.compile(r'product|name|title'))
            if name_elem:
                result['trade_name'] = name_elem.get_text(strip=True)
                if name_elem.name == 'a':
                    result['product_url'] = urljoin(BASE_URL, name_elem.get('href', ''))

            # Supplier
            supplier_elem = item.find(['span', 'div'], class_=re.compile(r'supplier|company|manufacturer'))
            if supplier_elem:
                result['supplier'] = supplier_elem.get_text(strip=True)

            # INCI
            inci_elem = item.find(['span', 'div'], class_=re.compile(r'inci'))
            if inci_elem:
                result['inci_name'] = inci_elem.get_text(strip=True)

            # Functions
            func_elems = item.find_all(['span', 'li'], class_=re.compile(r'function|category'))
            result['functions'] = [f.get_text(strip=True) for f in func_elems]

            # Description
            desc_elem = item.find(['p', 'div'], class_=re.compile(r'description|summary'))
            if desc_elem:
                result['description'] = desc_elem.get_text(strip=True)[:500]

            if result['trade_name'] or result['inci_name']:
                return result

        except Exception:
            pass

        return None

    def get_product_details(self, product_url: str) -> Optional[Dict]:
        """Get detailed product information from product page."""
        if not self.logged_in or not product_url:
            return None

        try:
            resp = self.session.get(product_url, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')

            product = {
                'product_url': product_url,
                'trade_name': '',
                'supplier': '',
                'inci_name': '',
                'cas_number': '',
                'functions': [],
                'description': '',
                'usage_level_min': '',
                'usage_level_max': '',
                'ph_min': '',
                'ph_max': '',
                'solubility': '',
                'appearance': '',
                'regulatory': [],
                'claims': [],
                'applications': [],
            }

            # Trade name (usually in h1 or title)
            title = soup.find('h1') or soup.find('title')
            if title:
                product['trade_name'] = title.get_text(strip=True).split('|')[0].strip()

            # Look for data in definition lists or tables
            for dl in soup.find_all(['dl', 'table']):
                rows = dl.find_all(['tr', 'div'])
                for row in rows:
                    label_elem = row.find(['dt', 'th', 'label'])
                    value_elem = row.find(['dd', 'td', 'span'])

                    if not label_elem or not value_elem:
                        continue

                    label = label_elem.get_text(strip=True).lower()
                    value = value_elem.get_text(strip=True)

                    if 'inci' in label:
                        product['inci_name'] = value
                    elif 'cas' in label:
                        product['cas_number'] = value
                    elif 'supplier' in label or 'company' in label or 'manufacturer' in label:
                        product['supplier'] = value
                    elif 'function' in label:
                        product['functions'].append(value)
                    elif 'usage' in label and 'level' in label:
                        # Parse usage level like "0.5 - 2.0%"
                        match = re.search(r'([\d.]+)\s*[-–]\s*([\d.]+)', value)
                        if match:
                            product['usage_level_min'] = match.group(1)
                            product['usage_level_max'] = match.group(2)
                        else:
                            match = re.search(r'([\d.]+)', value)
                            if match:
                                product['usage_level_max'] = match.group(1)
                    elif 'ph' in label:
                        match = re.search(r'([\d.]+)\s*[-–]\s*([\d.]+)', value)
                        if match:
                            product['ph_min'] = match.group(1)
                            product['ph_max'] = match.group(2)
                    elif 'solubil' in label:
                        product['solubility'] = value
                    elif 'appear' in label:
                        product['appearance'] = value
                    elif 'regulat' in label or 'compliance' in label:
                        product['regulatory'].append(value)
                    elif 'claim' in label:
                        product['claims'].append(value)
                    elif 'application' in label:
                        product['applications'].append(value)

            # Description
            desc = soup.find(['div', 'p'], class_=re.compile(r'description|overview|summary'))
            if desc:
                product['description'] = desc.get_text(strip=True)[:1000]

            return product

        except Exception as e:
            print(f"    Product detail error: {e}")
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
    print("UL PROSPECTOR INGREDIENT SCRAPER")
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
    scraper = ULProspectorScraper()

    # Login
    if not scraper.login():
        print("\nFailed to login. Please check your credentials in .env")
        return

    print()

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
        'trade_name',
        'supplier',
        'inci_name',
        'cas_number',
        'functions',
        'description',
        'usage_level_min',
        'usage_level_max',
        'ph_min',
        'ph_max',
        'solubility',
        'appearance',
        'regulatory',
        'claims',
        'applications',
        'product_url',
        'scraped_date',
    ]

    all_data = []

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        print(f"\nSearching UL Prospector for {len(ingredients)} ingredients...")
        print()

        found = 0
        not_found = 0

        for i, ingredient in enumerate(ingredients, 1):
            print(f"[{i}/{len(ingredients)}] {ingredient[:40]}...", end=' ')

            results = scraper.search_ingredient(ingredient)
            time.sleep(1)  # Rate limiting

            if results:
                found += 1
                print(f"Found {len(results)} result(s)")

                for result in results:
                    # Get detailed info if we have a product URL
                    if result.get('product_url') and not result.get('cas_number'):
                        details = scraper.get_product_details(result['product_url'])
                        if details:
                            result.update(details)
                        time.sleep(0.5)

                    row = {
                        'search_name': ingredient,
                        'trade_name': result.get('trade_name', ''),
                        'supplier': result.get('supplier', ''),
                        'inci_name': result.get('inci_name', ''),
                        'cas_number': result.get('cas_number', ''),
                        'functions': '; '.join(result.get('functions', [])),
                        'description': result.get('description', ''),
                        'usage_level_min': result.get('usage_level_min', ''),
                        'usage_level_max': result.get('usage_level_max', ''),
                        'ph_min': result.get('ph_min', ''),
                        'ph_max': result.get('ph_max', ''),
                        'solubility': result.get('solubility', ''),
                        'appearance': result.get('appearance', ''),
                        'regulatory': '; '.join(result.get('regulatory', [])),
                        'claims': '; '.join(result.get('claims', [])),
                        'applications': '; '.join(result.get('applications', [])),
                        'product_url': result.get('product_url', ''),
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
