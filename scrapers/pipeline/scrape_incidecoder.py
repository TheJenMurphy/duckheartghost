#!/usr/bin/env python3
"""
Scrape INCIDecoder for ingredient technical data.

INCIDecoder is a public cosmetic ingredient database - no login required!

Usage:
    python scrape_incidecoder.py --mystery     # Scrape mystery ingredients only
    python scrape_incidecoder.py --limit 50    # Scrape first 50 mystery ingredients
    python scrape_incidecoder.py --ingredient "Dimethicone"  # Single ingredient
    python scrape_incidecoder.py --all         # All ingredients
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
from urllib.parse import quote

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

import requests
from bs4 import BeautifulSoup
import functools
print = functools.partial(print, flush=True)

# INCIDecoder URLs
BASE_URL = "https://incidecoder.com"
SEARCH_URL = "https://incidecoder.com/ingredients"

# Output files
OUTPUT_CSV = Path(__file__).parent / 'data' / 'incidecoder_ingredients.csv'
OUTPUT_JSON = Path(__file__).parent / 'data' / 'incidecoder_ingredients.json'
MYSTERY_CSV = Path(__file__).parent / 'data' / 'pubmed_ingredient_fulltext.csv'


class INCIDecoderScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def search_ingredient(self, ingredient_name: str) -> Optional[Dict]:
        """Search INCIDecoder for an ingredient."""
        result = {
            'search_name': ingredient_name,
            'inci_name': '',
            'also_known_as': [],
            'what_it_does': [],
            'irritancy': '',
            'comedogenicity': '',
            'description': '',
            'cas_number': '',
            'category': '',
            'goodie_or_baddie': '',
            'products_count': 0,
            'url': '',
        }

        try:
            # Convert ingredient name to URL-friendly format
            slug = ingredient_name.lower()
            slug = re.sub(r'[^a-z0-9]+', '-', slug)
            slug = slug.strip('-')

            # Try direct URL first
            url = f"{SEARCH_URL}/{slug}"
            resp = self.session.get(url, timeout=30)

            if resp.status_code == 200 and 'ingredient' in resp.url:
                return self._parse_ingredient_page(resp.text, ingredient_name, resp.url)

            # If not found, try search
            search_resp = self.session.get(
                f"{BASE_URL}/search",
                params={'query': ingredient_name},
                timeout=30
            )

            if search_resp.status_code == 200:
                soup = BeautifulSoup(search_resp.text, 'html.parser')

                # Find ingredient links
                ingredient_links = soup.find_all('a', href=re.compile(r'/ingredients/'))
                for link in ingredient_links[:3]:
                    href = link.get('href', '')
                    if '/ingredients/' in href:
                        ing_url = f"{BASE_URL}{href}" if not href.startswith('http') else href
                        ing_resp = self.session.get(ing_url, timeout=30)
                        if ing_resp.status_code == 200:
                            parsed = self._parse_ingredient_page(ing_resp.text, ingredient_name, ing_url)
                            if parsed:
                                return parsed
                        time.sleep(0.3)

        except Exception as e:
            pass

        return None

    def _parse_ingredient_page(self, html: str, search_name: str, url: str) -> Optional[Dict]:
        """Parse an INCIDecoder ingredient page."""
        soup = BeautifulSoup(html, 'html.parser')

        result = {
            'search_name': search_name,
            'inci_name': '',
            'also_known_as': [],
            'what_it_does': [],
            'irritancy': '',
            'comedogenicity': '',
            'description': '',
            'cas_number': '',
            'category': '',
            'goodie_or_baddie': '',
            'products_count': 0,
            'url': url,
        }

        # INCI Name (h1 or title)
        h1 = soup.find('h1')
        if h1:
            result['inci_name'] = h1.get_text(strip=True)

        # What it does (functions)
        whatitdoes = soup.find('div', class_=re.compile(r'whatitdoes|functions'))
        if whatitdoes:
            funcs = whatitdoes.find_all(['span', 'a', 'li'])
            result['what_it_does'] = [f.get_text(strip=True) for f in funcs if f.get_text(strip=True)]

        # Also look for function tags/badges
        func_tags = soup.find_all(['span', 'div'], class_=re.compile(r'function|tag|label'))
        for tag in func_tags:
            func_text = tag.get_text(strip=True)
            if func_text and len(func_text) < 50 and func_text not in result['what_it_does']:
                result['what_it_does'].append(func_text)

        # Irritancy rating
        irritancy = soup.find(text=re.compile(r'irritancy', re.I))
        if irritancy:
            parent = irritancy.find_parent()
            if parent:
                rating = parent.get_text(strip=True)
                result['irritancy'] = rating[:50]

        # Comedogenicity
        comedogenic = soup.find(text=re.compile(r'comedogen', re.I))
        if comedogenic:
            parent = comedogenic.find_parent()
            if parent:
                rating = parent.get_text(strip=True)
                result['comedogenicity'] = rating[:50]

        # Description/summary
        desc = soup.find(['div', 'p'], class_=re.compile(r'description|summary|intro|content'))
        if desc:
            result['description'] = desc.get_text(strip=True)[:1000]

        # If no description, try first significant paragraph
        if not result['description']:
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if len(text) > 100:
                    result['description'] = text[:1000]
                    break

        # CAS Number
        cas_match = re.search(r'CAS[:\s#]*(\d{2,7}-\d{2}-\d)', html, re.I)
        if cas_match:
            result['cas_number'] = cas_match.group(1)

        # Also known as / synonyms
        aka = soup.find(text=re.compile(r'also known|synonym|other name', re.I))
        if aka:
            parent = aka.find_parent()
            if parent:
                text = parent.get_text()
                names = re.split(r'[,;]', text)
                result['also_known_as'] = [n.strip() for n in names if n.strip() and len(n.strip()) < 100][:10]

        # Goodie or baddie indicator
        goodie = soup.find(class_=re.compile(r'goodie|good|safe|green'))
        baddie = soup.find(class_=re.compile(r'baddie|bad|avoid|red'))
        if goodie:
            result['goodie_or_baddie'] = 'goodie'
        elif baddie:
            result['goodie_or_baddie'] = 'baddie'

        # Products count
        products_text = soup.find(text=re.compile(r'\d+\s*products?', re.I))
        if products_text:
            count_match = re.search(r'(\d+)\s*products?', products_text, re.I)
            if count_match:
                result['products_count'] = int(count_match.group(1))

        # Only return if we found meaningful data
        if result['inci_name'] or result['what_it_does'] or result['description']:
            return result

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


def get_all_ingredients() -> List[str]:
    """Get all ingredients from PubMed CSV."""
    ingredients = []

    if not MYSTERY_CSV.exists():
        return []

    with open(MYSTERY_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ingredients.append(row['name'])

    return ingredients


def main():
    print("=" * 70)
    print("INCIDECODER INGREDIENT SCRAPER")
    print("=" * 70)
    print()

    args = sys.argv[1:]

    # Parse arguments
    limit = None
    single_ingredient = None
    mystery_only = False
    all_ingredients = False

    for i, arg in enumerate(args):
        if arg == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1])
        elif arg == '--ingredient' and i + 1 < len(args):
            single_ingredient = args[i + 1]
        elif arg == '--mystery':
            mystery_only = True
        elif arg == '--all':
            all_ingredients = True

    if not mystery_only and not single_ingredient and limit is None and not all_ingredients:
        print(__doc__)
        return

    # Initialize scraper
    scraper = INCIDecoderScraper()

    # Get ingredients to scrape
    if single_ingredient:
        ingredients = [single_ingredient]
    elif all_ingredients:
        ingredients = get_all_ingredients()
        if limit:
            ingredients = ingredients[:limit]
        print(f"Scraping all {len(ingredients)} ingredients")
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
        'what_it_does',
        'irritancy',
        'comedogenicity',
        'description',
        'cas_number',
        'also_known_as',
        'goodie_or_baddie',
        'products_count',
        'url',
        'scraped_date',
    ]

    all_data = []

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        print(f"\nSearching INCIDecoder for {len(ingredients)} ingredients...")
        print()

        found = 0
        not_found = 0

        for i, ingredient in enumerate(ingredients, 1):
            print(f"[{i}/{len(ingredients)}] {ingredient[:40]}...", end=' ')

            result = scraper.search_ingredient(ingredient)
            time.sleep(0.5)  # Rate limiting

            if result and (result.get('inci_name') or result.get('what_it_does') or result.get('description')):
                found += 1
                funcs = result.get('what_it_does', [])
                print(f"Found! Functions: {', '.join(funcs[:3]) if funcs else 'see description'}")

                row = {
                    'search_name': ingredient,
                    'inci_name': result.get('inci_name', ''),
                    'what_it_does': '; '.join(result.get('what_it_does', [])),
                    'irritancy': result.get('irritancy', ''),
                    'comedogenicity': result.get('comedogenicity', ''),
                    'description': result.get('description', ''),
                    'cas_number': result.get('cas_number', ''),
                    'also_known_as': '; '.join(result.get('also_known_as', [])),
                    'goodie_or_baddie': result.get('goodie_or_baddie', ''),
                    'products_count': result.get('products_count', 0),
                    'url': result.get('url', ''),
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
