#!/usr/bin/env python3
"""
Scrape UL Prospector with MANUAL LOGIN.

This script opens a browser window for you to log in manually,
then continues with automated scraping once you're authenticated.

Usage:
    python scrape_prospector_manual_login.py --ingredient "Dimethicone"
    python scrape_prospector_manual_login.py --mystery
    python scrape_prospector_manual_login.py --limit 50
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


async def wait_for_manual_login(page: Page) -> bool:
    """Wait for user to manually log in."""
    print()
    print("=" * 70)
    print("MANUAL LOGIN REQUIRED")
    print("=" * 70)
    print()
    print("A browser window has opened to UL Prospector.")
    print("Please log in with your credentials:")
    print("  Email: info@versionorganic.com")
    print("  Password: Mega9288")
    print()
    print("Take your time logging in...")
    print("Script will wait 30 seconds after page loads, then start checking.")
    print()
    print("=" * 70)

    # Navigate to login page
    await page.goto(LOGIN_URL, wait_until='networkidle')

    # Give user 30 seconds to start logging in before we check anything
    print("Waiting 30 seconds for you to log in...")
    await page.wait_for_timeout(30000)

    # Now poll until login is detected
    max_wait = 300  # 5 more minutes max
    waited = 0
    while waited < max_wait:
        await page.wait_for_timeout(5000)  # Check every 5 seconds
        waited += 5

        current_url = page.url

        # Only consider logged in if we're on a search or dashboard page
        if '/search' in current_url.lower() or '/dashboard' in current_url.lower() or '/PersonalCare' in current_url:
            # Double-check by looking for search box
            try:
                search_box = await page.query_selector('input[type="search"], input[name*="search"], input[id*="search"], .search-input')
                if search_box:
                    print()
                    print("Login successful! Starting to scrape...")
                    print()
                    return True
            except:
                pass

        print(f"  Waiting for login... ({waited + 30}s total)")

    print("Timed out waiting for login.")
    return False


async def search_ingredient(page: Page, ingredient_name: str) -> List[Dict]:
    """Search for an ingredient."""
    results = []

    try:
        # Use INCI search
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

        # Visit each product page
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
            'applications': [],
        }

        # Get page content for regex parsing
        content = await page.content()

        # Trade name (h1)
        try:
            h1 = await page.query_selector('h1')
            if h1:
                product['trade_name'] = (await h1.inner_text()).strip()
        except:
            pass

        # INCI Name
        inci_match = re.search(r'INCI[^:]*:\s*([^<\n]+)', content, re.I)
        if inci_match:
            product['inci_name'] = inci_match.group(1).strip()[:200]

        # CAS Number
        cas_match = re.search(r'CAS[^:]*:\s*([\d-]+)', content, re.I)
        if cas_match:
            product['cas_number'] = cas_match.group(1).strip()

        # Supplier
        supplier_match = re.search(r'(?:Supplier|Manufacturer|Company)[^:]*:\s*([^<\n]+)', content, re.I)
        if supplier_match:
            product['supplier'] = supplier_match.group(1).strip()[:100]

        # Functions/Benefits
        func_matches = re.findall(r'(?:Function|Benefit)[^:]*:\s*([^<\n]+)', content, re.I)
        if func_matches:
            product['functions'] = [f.strip() for f in func_matches[:5]]

        # Usage level
        usage_match = re.search(r'(?:Usage|Use)\s*(?:Level|Rate)[^:]*:\s*([^<\n]+)', content, re.I)
        if usage_match:
            product['usage_level'] = usage_match.group(1).strip()[:100]

        # Description from meta or page
        try:
            meta = await page.query_selector('meta[name="description"]')
            if meta:
                desc = await meta.get_attribute('content')
                if desc:
                    product['description'] = desc[:500]
        except:
            pass

        # If no meta description, look for description section
        if not product['description']:
            desc_match = re.search(r'<div[^>]*class="[^"]*description[^"]*"[^>]*>([^<]+)', content, re.I)
            if desc_match:
                product['description'] = desc_match.group(1).strip()[:500]

        return product

    except Exception as e:
        print(f"    Detail error: {e}")
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


async def main_async():
    print("=" * 70)
    print("UL PROSPECTOR SCRAPER (MANUAL LOGIN)")
    print("=" * 70)
    print()

    args = sys.argv[1:]

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
        # Launch browser in NON-headless mode so user can login
        browser = await p.chromium.launch(
            headless=False,  # VISIBLE browser window
            slow_mo=100,     # Slow down for human-like behavior
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        # Wait for manual login
        await wait_for_manual_login(page)

        fieldnames = [
            'search_name', 'trade_name', 'supplier', 'inci_name',
            'cas_number', 'functions', 'description', 'usage_level',
            'applications', 'product_url', 'scraped_date',
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
                            'applications': '; '.join(result.get('applications', [])),
                            'product_url': result.get('product_url', ''),
                            'scraped_date': datetime.now().isoformat(),
                        }
                        writer.writerow(row)
                        all_data.append(row)
                else:
                    not_found += 1
                    print("Not found")

                # Small delay between searches
                await page.wait_for_timeout(500)

        await browser.close()

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


def main():
    asyncio.run(main_async())


if __name__ == '__main__':
    main()
