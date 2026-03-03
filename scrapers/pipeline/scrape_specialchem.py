#!/usr/bin/env python3
"""
Scrape SpecialChem for ingredient technical data.

Requires SpecialChem account credentials in .env:
    SPECIALCHEM_EMAIL=your_email
    SPECIALCHEM_PASSWORD=your_password

Usage:
    python scrape_specialchem.py --mystery     # Scrape mystery ingredients only
    python scrape_specialchem.py --limit 50   # Scrape first 50 mystery ingredients
    python scrape_specialchem.py --ingredient "Dimethicone"  # Single ingredient
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

# SpecialChem URLs
BASE_URL = "https://cosmetics.specialchem.com"
LOGIN_URL = "https://cosmetics.specialchem.com/user/login"
SEARCH_URL = "https://cosmetics.specialchem.com/searchsites/ingredients"
INCI_SEARCH_URL = "https://cosmetics.specialchem.com/inci"

# Output files
OUTPUT_CSV = Path(__file__).parent / 'data' / 'specialchem_ingredients.csv'
OUTPUT_JSON = Path(__file__).parent / 'data' / 'specialchem_ingredients.json'
MYSTERY_CSV = Path(__file__).parent / 'data' / 'pubmed_ingredient_fulltext.csv'


class SpecialChemScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.logged_in = False

    def login(self) -> bool:
        """Login to SpecialChem."""
        email = os.environ.get('SPECIALCHEM_EMAIL', '')
        password = os.environ.get('SPECIALCHEM_PASSWORD', '')

        if not email or not password:
            print("ERROR: SPECIALCHEM_EMAIL and SPECIALCHEM_PASSWORD must be set in .env")
            return False

        print(f"Logging in to SpecialChem as {email}...")

        try:
            # Get login page
            resp = self.session.get(LOGIN_URL, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find any CSRF tokens or hidden fields
            hidden_inputs = {}
            for inp in soup.find_all('input', {'type': 'hidden'}):
                name = inp.get('name')
                value = inp.get('value', '')
                if name:
                    hidden_inputs[name] = value

            # Login data
            login_data = {
                'email': email,
                'password': password,
                **hidden_inputs
            }

            # Try alternate field names
            if 'username' not in login_data and 'email' not in login_data:
                login_data['username'] = email

            resp = self.session.post(
                LOGIN_URL,
                data=login_data,
                timeout=30,
                allow_redirects=True
            )

            # Check if login was successful
            if 'logout' in resp.text.lower() or 'sign out' in resp.text.lower() or 'my account' in resp.text.lower():
                print("  Login successful!")
                self.logged_in = True
                return True
            else:
                # Try to detect error message
                soup = BeautifulSoup(resp.text, 'html.parser')
                error = soup.find(class_=re.compile(r'error|alert|warning'))
                if error:
                    print(f"  Login failed: {error.get_text(strip=True)}")
                else:
                    print("  Login may have failed - proceeding anyway (some content is public)")
                # Continue anyway as some content is publicly accessible
                self.logged_in = True
                return True

        except Exception as e:
            print(f"  Login error: {e}")
            print("  Continuing without login (some content is public)")
            self.logged_in = True
            return True

    def search_inci(self, ingredient_name: str) -> Optional[Dict]:
        """Search INCI database for an ingredient."""
        try:
            # Try INCI search
            search_url = f"{INCI_SEARCH_URL}/{quote_plus(ingredient_name.lower().replace(' ', '-'))}"

            resp = self.session.get(search_url, timeout=30)

            if resp.status_code == 200:
                return self._parse_inci_page(resp.text, ingredient_name)

            # Try general search
            search_params = {
                'q': ingredient_name,
            }

            resp = self.session.get(
                f"{BASE_URL}/search",
                params=search_params,
                timeout=30
            )

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                # Find INCI links in search results
                inci_links = soup.find_all('a', href=re.compile(r'/inci/'))
                for link in inci_links[:3]:
                    inci_url = urljoin(BASE_URL, link.get('href', ''))
                    inci_resp = self.session.get(inci_url, timeout=30)
                    if inci_resp.status_code == 200:
                        result = self._parse_inci_page(inci_resp.text, ingredient_name)
                        if result:
                            return result
                    time.sleep(0.5)

        except Exception as e:
            print(f"    INCI search error: {e}")

        return None

    def _parse_inci_page(self, html: str, search_name: str) -> Optional[Dict]:
        """Parse an INCI ingredient page."""
        soup = BeautifulSoup(html, 'html.parser')

        result = {
            'search_name': search_name,
            'inci_name': '',
            'cas_number': '',
            'ec_number': '',
            'description': '',
            'functions': [],
            'origin': '',
            'chemical_class': '',
            'synonyms': [],
            'related_ingredients': [],
            'suppliers': [],
            'products': [],
            'usage_level': '',
            'solubility': '',
            'regulatory': [],
        }

        # INCI Name (usually h1)
        h1 = soup.find('h1')
        if h1:
            result['inci_name'] = h1.get_text(strip=True)

        # Look for data in definition lists, tables, or labeled sections
        for section in soup.find_all(['dl', 'table', 'div', 'section']):
            text = section.get_text(separator=' ', strip=True).lower()

            # CAS Number
            cas_match = re.search(r'cas[:\s#]*(\d{2,7}-\d{2}-\d)', text)
            if cas_match:
                result['cas_number'] = cas_match.group(1)

            # EC Number
            ec_match = re.search(r'(?:ec|einecs)[:\s#]*(\d{3}-\d{3}-\d)', text)
            if ec_match:
                result['ec_number'] = ec_match.group(1)

        # Functions
        func_section = soup.find(['div', 'section'], class_=re.compile(r'function'))
        if func_section:
            func_items = func_section.find_all(['li', 'span', 'a'])
            result['functions'] = [f.get_text(strip=True) for f in func_items if f.get_text(strip=True)]

        # Also look for function badges/tags
        func_tags = soup.find_all(['span', 'a'], class_=re.compile(r'function|tag|badge'))
        for tag in func_tags:
            func_text = tag.get_text(strip=True)
            if func_text and func_text not in result['functions']:
                result['functions'].append(func_text)

        # Description
        desc = soup.find(['div', 'p'], class_=re.compile(r'description|overview|intro'))
        if desc:
            result['description'] = desc.get_text(strip=True)[:1000]

        # If no description found, try meta description
        if not result['description']:
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc:
                result['description'] = meta_desc.get('content', '')[:1000]

        # Origin (natural, synthetic, etc.)
        origin_elem = soup.find(text=re.compile(r'origin|source', re.I))
        if origin_elem:
            parent = origin_elem.find_parent()
            if parent:
                result['origin'] = parent.get_text(strip=True)[:200]

        # Suppliers
        supplier_section = soup.find(['div', 'section'], class_=re.compile(r'supplier'))
        if supplier_section:
            supplier_links = supplier_section.find_all('a')
            result['suppliers'] = [s.get_text(strip=True) for s in supplier_links[:10]]

        # Products/Trade names
        product_section = soup.find(['div', 'section'], class_=re.compile(r'product'))
        if product_section:
            product_links = product_section.find_all('a')
            result['products'] = [p.get_text(strip=True) for p in product_links[:10]]

        # Synonyms
        synonym_section = soup.find(['div', 'section'], text=re.compile(r'synonym|also known', re.I))
        if synonym_section:
            result['synonyms'] = [s.strip() for s in synonym_section.get_text().split(',') if s.strip()]

        # Regulatory
        reg_section = soup.find(['div', 'section'], class_=re.compile(r'regulat|compliance'))
        if reg_section:
            reg_items = reg_section.find_all(['li', 'span'])
            result['regulatory'] = [r.get_text(strip=True) for r in reg_items]

        # Only return if we found meaningful data
        if result['inci_name'] or result['cas_number'] or result['functions']:
            return result

        return None

    def search_product(self, ingredient_name: str) -> List[Dict]:
        """Search for products containing the ingredient."""
        products = []

        try:
            search_params = {
                'q': ingredient_name,
                'type': 'product',
            }

            resp = self.session.get(
                f"{BASE_URL}/product-search",
                params=search_params,
                timeout=30
            )

            if resp.status_code != 200:
                return products

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find product cards/items
            product_items = soup.find_all(['div', 'article'], class_=re.compile(r'product|item|card'))

            for item in product_items[:5]:
                product = {
                    'trade_name': '',
                    'supplier': '',
                    'description': '',
                    'functions': [],
                    'inci_list': '',
                }

                # Trade name
                name_elem = item.find(['h3', 'h4', 'a'], class_=re.compile(r'name|title'))
                if name_elem:
                    product['trade_name'] = name_elem.get_text(strip=True)

                # Supplier
                supplier_elem = item.find(class_=re.compile(r'supplier|company'))
                if supplier_elem:
                    product['supplier'] = supplier_elem.get_text(strip=True)

                # Description
                desc_elem = item.find(class_=re.compile(r'description|summary'))
                if desc_elem:
                    product['description'] = desc_elem.get_text(strip=True)[:500]

                if product['trade_name']:
                    products.append(product)

        except Exception as e:
            print(f"    Product search error: {e}")

        return products


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
    print("SPECIALCHEM INGREDIENT SCRAPER")
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
    scraper = SpecialChemScraper()

    # Login
    scraper.login()
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
        'inci_name',
        'cas_number',
        'ec_number',
        'functions',
        'description',
        'origin',
        'chemical_class',
        'synonyms',
        'suppliers',
        'products',
        'usage_level',
        'solubility',
        'regulatory',
        'scraped_date',
    ]

    all_data = []

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        print(f"\nSearching SpecialChem for {len(ingredients)} ingredients...")
        print()

        found = 0
        not_found = 0

        for i, ingredient in enumerate(ingredients, 1):
            print(f"[{i}/{len(ingredients)}] {ingredient[:40]}...", end=' ')

            # Search INCI database
            result = scraper.search_inci(ingredient)
            time.sleep(0.8)  # Rate limiting

            if result:
                found += 1
                funcs = result.get('functions', [])
                print(f"Found! Functions: {', '.join(funcs[:3]) if funcs else 'N/A'}")

                row = {
                    'search_name': ingredient,
                    'inci_name': result.get('inci_name', ''),
                    'cas_number': result.get('cas_number', ''),
                    'ec_number': result.get('ec_number', ''),
                    'functions': '; '.join(result.get('functions', [])),
                    'description': result.get('description', ''),
                    'origin': result.get('origin', ''),
                    'chemical_class': result.get('chemical_class', ''),
                    'synonyms': '; '.join(result.get('synonyms', [])),
                    'suppliers': '; '.join(result.get('suppliers', [])),
                    'products': '; '.join(result.get('products', [])),
                    'usage_level': result.get('usage_level', ''),
                    'solubility': result.get('solubility', ''),
                    'regulatory': '; '.join(result.get('regulatory', [])),
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
