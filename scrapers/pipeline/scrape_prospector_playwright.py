#!/usr/bin/env python3
"""
Scrape UL Prospector using Playwright (better bot detection bypass).

Usage:
    python scrape_prospector_playwright.py --ingredient "Dimethicone"
    python scrape_prospector_playwright.py --limit 20
    python scrape_prospector_playwright.py --mystery
"""

import os
import sys
import time
import csv
import re
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

from playwright.async_api import async_playwright, Page
import functools
print = functools.partial(print, flush=True)

# URLs
BASE_URL = "https://www.ulprospector.com"
LOGIN_URL = "https://www.ulprospector.com/en/na/PersonalCare/Account/Login"
SEARCH_URL = "https://www.ulprospector.com/en/na/PersonalCare/search"

# Output files
OUTPUT_CSV = Path(__file__).parent / 'data' / 'ul_prospector_ingredients.csv'
OUTPUT_JSON = Path(__file__).parent / 'data' / 'ul_prospector_ingredients.json'
MYSTERY_CSV = Path(__file__).parent / 'data' / 'pubmed_ingredient_fulltext.csv'


async def login(page: Page) -> bool:
    """Login to UL Prospector."""
    email = os.environ.get('UL_PROSPECTOR_EMAIL', '')
    password = os.environ.get('UL_PROSPECTOR_PASSWORD', '')

    if not email or not password:
        print("ERROR: UL_PROSPECTOR_EMAIL and UL_PROSPECTOR_PASSWORD must be set in .env")
        return False

    print(f"Logging in to UL Prospector as {email}...")

    try:
        await page.goto(LOGIN_URL, wait_until='networkidle')
        await page.wait_for_timeout(2000)

        # Fill email
        await page.fill('input[name="Email"]', email)
        await page.wait_for_timeout(500)

        # Fill password
        await page.fill('input[name="Password"]', password)
        await page.wait_for_timeout(500)

        # Click submit
        await page.click('button[type="submit"], input[type="submit"]')
        await page.wait_for_timeout(3000)

        # Check if login successful
        if 'login' not in page.url.lower():
            print("  Login successful!")
            return True
        else:
            print("  Login may have failed")
            return False

    except Exception as e:
        print(f"  Login error: {e}")
        return False


async def search_ingredient(page: Page, ingredient_name: str) -> List[Dict]:
    """Search for an ingredient."""
    results = []

    try:
        search_url = f"{SEARCH_URL}?k={ingredient_name.replace(' ', '+')}&searchType=INCI"
        await page.goto(search_url, wait_until='networkidle')
        await page.wait_for_timeout(2000)

        # Find product links
        product_links = await page.query_selector_all('a[href*="/Product/"]')

        urls = []
        for link in product_links[:5]:
            href = await link.get_attribute('href')
            if href and '/Product/' in href:
                full_url = href if href.startswith('http') else f"{BASE_URL}{href}"
                if full_url not in urls:
                    urls.append(full_url)

        # Visit each product
        for url in urls[:3]:
            product = await get_product_details(page, url)
            if product:
                results.append(product)
            await page.wait_for_timeout(1000)

    except Exception as e:
        print(f"    Search error: {e}")

    return results


async def get_product_details(page: Page, url: str) -> Optional[Dict]:
    """Get product details from product page."""
    try:
        await page.goto(url, wait_until='networkidle')
        await page.wait_for_timeout(1500)

        product = {
            'product_url': url,
            'trade_name': '',
            'supplier': '',
            'inci_name': '',
            'cas_number': '',
            'functions': [],
            'description': '',
            'usage_level': '',
        }

        # Get page content
        content = await page.content()

        # Trade name
        try:
            h1 = await page.query_selector('h1')
            if h1:
                product['trade_name'] = await h1.inner_text()
        except:
            pass

        # Extract data using regex on page content
        inci_match = re.search(r'INCI[^:]*:\s*([^<\n]+)', content, re.I)
        if inci_match:
            product['inci_name'] = inci_match.group(1).strip()[:200]

        cas_match = re.search(r'CAS[^:]*:\s*([\d-]+)', content, re.I)
        if cas_match:
            product['cas_number'] = cas_match.group(1).strip()

        supplier_match = re.search(r'(?:Supplier|Company)[^:]*:\s*([^<\n]+)', content, re.I)
        if supplier_match:
            product['supplier'] = supplier_match.group(1).strip()[:100]

        # Description from meta
        try:
            meta = await page.query_selector('meta[name="description"]')
            if meta:
                product['description'] = (await meta.get_attribute('content'))[:500]
        except:
            pass

        return product

    except Exception as e:
        print(f"    Detail error: {e}")
        return None


def get_mystery_ingredients(limit: Optional[int] = None) -> List[str]:
    """Get ingredients with no PubMed data."""
    mystery = []

    if not MYSTERY_CSV.exists():
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


async def main_async():
    print("=" * 70)
    print("UL PROSPECTOR PLAYWRIGHT SCRAPER")
    print("=" * 70)
    print()

    args = sys.argv[1:]

    limit = None
    single_ingredient = None
    mystery_only = False
    headless = '--headless' in args

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

    # Get ingredients
    if single_ingredient:
        ingredients = [single_ingredient]
    else:
        ingredients = get_mystery_ingredients(limit)
        print(f"Found {len(ingredients)} mystery ingredients")

    if not ingredients:
        print("No ingredients to process")
        return

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()

        # Login
        if not await login(page):
            print("\nLogin failed")
            await browser.close()
            return

        print()

        fieldnames = [
            'search_name', 'trade_name', 'supplier', 'inci_name',
            'cas_number', 'functions', 'description', 'usage_level',
            'product_url', 'scraped_date',
        ]

        all_data = []

        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            print(f"Searching for {len(ingredients)} ingredients...")
            print()

            found = 0
            not_found = 0

            for i, ingredient in enumerate(ingredients, 1):
                print(f"[{i}/{len(ingredients)}] {ingredient[:40]}...", end=' ')

                results = await search_ingredient(page, ingredient)

                if results:
                    found += 1
                    print(f"Found {len(results)} result(s)")

                    for result in results:
                        row = {
                            'search_name': ingredient,
                            'trade_name': result.get('trade_name', ''),
                            'supplier': result.get('supplier', ''),
                            'inci_name': result.get('inci_name', ''),
                            'cas_number': result.get('cas_number', ''),
                            'functions': '; '.join(result.get('functions', [])),
                            'description': result.get('description', ''),
                            'usage_level': result.get('usage_level', ''),
                            'product_url': result.get('product_url', ''),
                            'scraped_date': datetime.now().isoformat(),
                        }
                        writer.writerow(row)
                        all_data.append(row)
                else:
                    not_found += 1
                    print("Not found")

        await browser.close()

        # Save JSON
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

        print()
        print("=" * 70)
        print(f"Found: {found} | Not found: {not_found}")
        print(f"Output: {OUTPUT_CSV}")


def main():
    asyncio.run(main_async())


if __name__ == '__main__':
    main()
