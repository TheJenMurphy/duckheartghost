#!/usr/bin/env python3
"""
Scrape UL Prospector using browser automation (Selenium).

This version uses a real browser to bypass bot protection.

Requires:
    pip install selenium webdriver-manager

Usage:
    python scrape_ul_prospector_browser.py --ingredient "Dimethicone"
    python scrape_ul_prospector_browser.py --limit 20
    python scrape_ul_prospector_browser.py --mystery
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

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    ChromeDriverManager = None

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


class ULProspectorBrowserScraper:
    def __init__(self, headless: bool = False):
        self.driver = None
        self.headless = headless
        self.logged_in = False

    def start_browser(self):
        """Start Chrome browser."""
        options = Options()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Use webdriver-manager if available, otherwise expect chromedriver in PATH
        if ChromeDriverManager:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        else:
            self.driver = webdriver.Chrome(options=options)

        # Make automation less detectable
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("Browser started")

    def login(self) -> bool:
        """Login to UL Prospector."""
        email = os.environ.get('UL_PROSPECTOR_EMAIL', '')
        password = os.environ.get('UL_PROSPECTOR_PASSWORD', '')

        if not email or not password:
            print("ERROR: UL_PROSPECTOR_EMAIL and UL_PROSPECTOR_PASSWORD must be set in .env")
            return False

        print(f"Logging in to UL Prospector as {email}...")

        try:
            self.driver.get(LOGIN_URL)
            time.sleep(2)

            # Wait for login form
            wait = WebDriverWait(self.driver, 15)

            # Find and fill email
            email_field = wait.until(EC.presence_of_element_located((By.NAME, "Email")))
            email_field.clear()
            email_field.send_keys(email)
            time.sleep(0.5)

            # Find and fill password
            password_field = self.driver.find_element(By.NAME, "Password")
            password_field.clear()
            password_field.send_keys(password)
            time.sleep(0.5)

            # Submit
            password_field.send_keys(Keys.RETURN)
            time.sleep(3)

            # Check if login successful
            if 'login' not in self.driver.current_url.lower():
                print("  Login successful!")
                self.logged_in = True
                return True
            else:
                print("  Login may have failed - check browser")
                return False

        except Exception as e:
            print(f"  Login error: {e}")
            return False

    def search_ingredient(self, ingredient_name: str) -> List[Dict]:
        """Search for an ingredient."""
        results = []

        try:
            # Navigate to search
            search_url = f"{SEARCH_URL}?k={ingredient_name.replace(' ', '+')}&searchType=INCI"
            self.driver.get(search_url)
            time.sleep(2)

            # Wait for results
            wait = WebDriverWait(self.driver, 10)

            # Look for product results
            try:
                product_links = wait.until(EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "a[href*='/Product/']")
                ))
            except TimeoutException:
                product_links = []

            # Get first few product links
            urls = []
            for link in product_links[:5]:
                href = link.get_attribute('href')
                if href and '/Product/' in href and href not in urls:
                    urls.append(href)

            # Visit each product page
            for url in urls[:3]:
                product_data = self.get_product_details(url)
                if product_data:
                    results.append(product_data)
                time.sleep(1)

        except Exception as e:
            print(f"    Search error: {e}")

        return results

    def get_product_details(self, url: str) -> Optional[Dict]:
        """Get product details from product page."""
        try:
            self.driver.get(url)
            time.sleep(2)

            product = {
                'product_url': url,
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

            # Get page content
            page_text = self.driver.page_source

            # Trade name from h1
            try:
                h1 = self.driver.find_element(By.TAG_NAME, 'h1')
                product['trade_name'] = h1.text.strip()
            except:
                pass

            # Look for data in the page
            # INCI Name
            inci_match = re.search(r'INCI[^:]*:\s*([^<\n]+)', page_text, re.I)
            if inci_match:
                product['inci_name'] = inci_match.group(1).strip()

            # CAS Number
            cas_match = re.search(r'CAS[^:]*:\s*([\d-]+)', page_text, re.I)
            if cas_match:
                product['cas_number'] = cas_match.group(1).strip()

            # Supplier
            supplier_match = re.search(r'(?:Supplier|Company|Manufacturer)[^:]*:\s*([^<\n]+)', page_text, re.I)
            if supplier_match:
                product['supplier'] = supplier_match.group(1).strip()

            # Functions - look for function section
            func_matches = re.findall(r'(?:Function|Category)[^:]*:\s*([^<\n]+)', page_text, re.I)
            product['functions'] = [f.strip() for f in func_matches if f.strip()]

            # Usage level
            usage_match = re.search(r'(?:Usage|Concentration|Level)[^:]*:\s*([\d.]+\s*[-–]\s*[\d.]+\s*%?)', page_text, re.I)
            if usage_match:
                levels = re.findall(r'[\d.]+', usage_match.group(1))
                if len(levels) >= 2:
                    product['usage_level_min'] = levels[0]
                    product['usage_level_max'] = levels[1]
                elif levels:
                    product['usage_level_max'] = levels[0]

            # pH
            ph_match = re.search(r'pH[^:]*:\s*([\d.]+\s*[-–]\s*[\d.]+)', page_text, re.I)
            if ph_match:
                ph_values = re.findall(r'[\d.]+', ph_match.group(1))
                if len(ph_values) >= 2:
                    product['ph_min'] = ph_values[0]
                    product['ph_max'] = ph_values[1]

            # Description - try to get from meta or first paragraph
            try:
                desc_elem = self.driver.find_element(By.CSS_SELECTOR, 'meta[name="description"]')
                product['description'] = desc_elem.get_attribute('content')[:500]
            except:
                pass

            return product

        except Exception as e:
            print(f"    Product detail error: {e}")
            return None

    def close(self):
        """Close browser."""
        if self.driver:
            self.driver.quit()


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
    print("UL PROSPECTOR BROWSER SCRAPER")
    print("=" * 70)
    print()

    args = sys.argv[1:]

    # Parse arguments
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

    # Initialize scraper
    scraper = ULProspectorBrowserScraper(headless=headless)

    try:
        # Start browser
        scraper.start_browser()

        # Login
        if not scraper.login():
            print("\nFailed to login. Please check your credentials.")
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

                time.sleep(1)  # Rate limiting

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

    finally:
        scraper.close()


if __name__ == '__main__':
    main()
