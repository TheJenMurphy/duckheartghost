#!/usr/bin/env python3
"""
Retailer Product Data Scraper

Scrapes rich product data from:
- Sephora
- Credo Beauty
- Brand websites (Shopify)

Extracts:
- Detailed descriptions
- How to use instructions
- Key ingredients
- Benefits/claims
- Ratings & reviews
- Product images

Usage:
    python scrape_retailer_data.py "https://www.sephora.com/product/..."
    python scrape_retailer_data.py "https://credobeauty.com/products/..."
    python scrape_retailer_data.py --brand-url "https://brand.com/products/..."
"""

import argparse
import json
import re
import sys
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Install: pip install requests beautifulsoup4")
    sys.exit(1)


# Common headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


class RetailerScraper:
    """Base class for retailer scrapers."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._last_request = 0
        self._min_delay = 1.0  # Seconds between requests

    def _rate_limit(self):
        """Enforce minimum delay between requests."""
        elapsed = time.time() - self._last_request
        if elapsed < self._min_delay:
            time.sleep(self._min_delay - elapsed)
        self._last_request = time.time()

    def _get_page(self, url: str, timeout: int = 15) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        self._rate_limit()
        try:
            resp = self.session.get(url, timeout=timeout)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, 'html.parser')
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None


class SephoraScraper(RetailerScraper):
    """Scraper for Sephora product pages."""

    def scrape_product(self, url: str) -> Dict:
        """Scrape product data from Sephora."""
        soup = self._get_page(url)
        if not soup:
            return {'error': 'Failed to fetch page'}

        data = {
            'source': 'sephora',
            'url': url,
        }

        # Product name
        name_elem = soup.select_one('h1[data-at="product_name"]') or soup.find('h1')
        if name_elem:
            data['name'] = name_elem.get_text(strip=True)

        # Brand name
        brand_elem = soup.select_one('[data-at="brand_name"]') or soup.select_one('.brand-name')
        if brand_elem:
            data['brand'] = brand_elem.get_text(strip=True)

        # Price
        price_elem = soup.select_one('[data-at="price"]') or soup.select_one('.css-0')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'\$?([\d.]+)', price_text)
            if price_match:
                data['price'] = float(price_match.group(1))

        # Rating
        rating_elem = soup.select_one('[data-at="star_rating"]') or soup.select_one('.css-zj7z9')
        if rating_elem:
            rating_text = rating_elem.get('aria-label', '') or rating_elem.get_text()
            rating_match = re.search(r'([\d.]+)\s*(out of|/)\s*5', rating_text)
            if rating_match:
                data['rating'] = float(rating_match.group(1))

        # Review count
        review_elem = soup.select_one('[data-at="number_of_reviews"]')
        if review_elem:
            review_text = review_elem.get_text(strip=True)
            review_match = re.search(r'(\d+)', review_text.replace(',', ''))
            if review_match:
                data['review_count'] = int(review_match.group(1))

        # Description sections
        # About the Product
        about_section = soup.select_one('[data-at="about"]') or soup.find(
            lambda tag: tag.name in ['div', 'section'] and
            'about' in (tag.get('class', []) + [tag.get('id', '')]))
        if about_section:
            data['description'] = about_section.get_text(separator=' ', strip=True)[:2000]

        # How to Use
        how_to_section = soup.find(
            lambda tag: tag.name in ['div', 'section'] and
            any('how' in str(c).lower() and 'use' in str(c).lower()
                for c in [tag.get('class', []), tag.get('id', ''), tag.get('data-at', '')]))
        if how_to_section:
            data['how_to_use'] = how_to_section.get_text(separator=' ', strip=True)[:1000]

        # Ingredients
        ingredients_section = soup.find(
            lambda tag: tag.name in ['div', 'section'] and
            'ingredient' in str(tag.get('class', []) + [tag.get('id', '')]).lower())
        if ingredients_section:
            data['ingredients'] = ingredients_section.get_text(separator=' ', strip=True)[:3000]

        # Highlighted ingredients (key ingredients)
        highlight_items = soup.select('[data-at="ingredient_callout"]') or soup.select('.ingredient-callout')
        if highlight_items:
            data['key_ingredients'] = [item.get_text(strip=True) for item in highlight_items[:5]]

        # Product claims/benefits
        claims = soup.select('[data-at="product_details_claim"]') or soup.select('.claim-item')
        if claims:
            data['claims'] = [claim.get_text(strip=True) for claim in claims]

        # Categories/tags
        breadcrumbs = soup.select('.css-1e2c5n2 a') or soup.select('[data-at="breadcrumb"] a')
        if breadcrumbs:
            data['categories'] = [bc.get_text(strip=True) for bc in breadcrumbs]

        # Product images
        images = []
        for img in soup.select('[data-at="product_image"] img') or soup.select('.product-image img'):
            src = img.get('src') or img.get('data-src')
            if src and src not in images:
                # Get larger version
                src = re.sub(r'_\d+x\d+', '_1000x1000', src)
                images.append(src)
        data['images'] = images[:10]

        return data


class CredoBeautyScraper(RetailerScraper):
    """Scraper for Credo Beauty product pages."""

    def scrape_product(self, url: str) -> Dict:
        """Scrape product data from Credo Beauty."""
        soup = self._get_page(url)
        if not soup:
            return {'error': 'Failed to fetch page'}

        data = {
            'source': 'credo',
            'url': url,
        }

        # Try Shopify JSON first (Credo uses Shopify)
        json_url = url.split('?')[0]
        if not json_url.endswith('.json'):
            json_url += '.json'

        try:
            resp = self.session.get(json_url, timeout=10)
            if resp.status_code == 200:
                product_json = resp.json().get('product', {})
                data['name'] = product_json.get('title', '')
                data['vendor'] = product_json.get('vendor', '')
                data['brand'] = product_json.get('vendor', '')
                data['product_type'] = product_json.get('product_type', '')
                data['tags'] = product_json.get('tags', [])

                # Get body HTML for parsing
                body_html = product_json.get('body_html', '')
                if body_html:
                    body_soup = BeautifulSoup(body_html, 'html.parser')
                    data['description'] = body_soup.get_text(separator=' ', strip=True)[:2000]

                    # Extract sections from body
                    data.update(self._extract_sections_from_html(body_html))

                # Get variants for price
                variants = product_json.get('variants', [])
                if variants:
                    data['price'] = float(variants[0].get('price', 0))
                    data['size'] = variants[0].get('title', '')

                # Get images
                images = []
                for img in product_json.get('images', [])[:10]:
                    src = img.get('src', '')
                    if src:
                        # Get large version
                        src = re.sub(r'_\d+x\d+', '', src.split('?')[0])
                        images.append(src)
                data['images'] = images

        except Exception as e:
            print(f"JSON endpoint failed: {e}")

        # Fall back to HTML parsing if needed
        if not data.get('name'):
            name_elem = soup.find('h1') or soup.select_one('.product-title')
            if name_elem:
                data['name'] = name_elem.get_text(strip=True)

        # Credo-specific: Clean ingredients callout
        clean_section = soup.select_one('.credo-clean') or soup.find(
            lambda tag: 'credo' in str(tag.get('class', [])).lower() and 'clean' in str(tag.get('class', [])).lower())
        if clean_section:
            data['clean_certification'] = clean_section.get_text(strip=True)

        # Credo-specific: Ingredient highlights
        highlights = soup.select('.ingredient-highlight') or soup.select('[data-ingredient]')
        if highlights:
            data['key_ingredients'] = [h.get_text(strip=True) for h in highlights[:5]]

        return data

    def _extract_sections_from_html(self, html: str) -> Dict:
        """Extract structured sections from product HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        sections = {}

        text = soup.get_text(separator='\n', strip=True)
        lines = text.split('\n')

        current_section = None
        section_content = []

        section_headers = {
            'how to use': 'how_to_use',
            'directions': 'how_to_use',
            'ingredients': 'ingredients',
            'full ingredients': 'ingredients',
            'key ingredients': 'key_ingredients_text',
            'benefits': 'benefits',
            'what it does': 'benefits',
            'about': 'about',
            'the formula': 'formula',
            'why we love it': 'why_love',
        }

        for line in lines:
            line_lower = line.lower().strip()

            # Check if this is a section header
            for header, section_key in section_headers.items():
                if header in line_lower and len(line) < 50:
                    # Save previous section
                    if current_section and section_content:
                        sections[current_section] = ' '.join(section_content)[:1500]
                    current_section = section_key
                    section_content = []
                    break
            else:
                if current_section and line.strip():
                    section_content.append(line.strip())

        # Save last section
        if current_section and section_content:
            sections[current_section] = ' '.join(section_content)[:1500]

        return sections


class ShopifyBrandScraper(RetailerScraper):
    """Scraper for Shopify-based brand websites."""

    def scrape_product(self, url: str) -> Dict:
        """Scrape product data from a Shopify store."""
        data = {
            'source': 'shopify_brand',
            'url': url,
        }

        # Try JSON endpoint first
        json_url = url.split('?')[0]
        if not json_url.endswith('.json'):
            json_url += '.json'

        try:
            self._rate_limit()
            resp = self.session.get(json_url, timeout=10)
            if resp.status_code == 200:
                product = resp.json().get('product', {})

                data['name'] = product.get('title', '')
                data['brand'] = product.get('vendor', '')
                data['product_type'] = product.get('product_type', '')
                data['tags'] = product.get('tags', [])
                data['handle'] = product.get('handle', '')

                # Parse body HTML
                body_html = product.get('body_html', '')
                if body_html:
                    soup = BeautifulSoup(body_html, 'html.parser')
                    full_text = soup.get_text(separator='\n', strip=True)
                    data['description'] = full_text[:2000]

                    # Extract structured sections
                    data.update(self._parse_product_description(full_text))

                    # Look for ingredients specifically
                    ingredients = self._extract_ingredients(full_text)
                    if ingredients:
                        data['ingredients'] = ingredients

                # Variants/Price
                variants = product.get('variants', [])
                if variants:
                    data['price'] = float(variants[0].get('price', 0))
                    data['compare_at_price'] = variants[0].get('compare_at_price')
                    data['sku'] = variants[0].get('sku', '')

                    # Size from variant title
                    size = variants[0].get('title', '')
                    if size and size != 'Default Title':
                        data['size'] = size

                # Images
                images = []
                for img in product.get('images', [])[:10]:
                    src = img.get('src', '')
                    if src:
                        # Remove size suffix for full resolution
                        src = re.sub(r'_\d+x\d*\.', '.', src.split('?')[0])
                        images.append(src)
                data['images'] = images

                # Options (for shade ranges, etc.)
                options = product.get('options', [])
                for opt in options:
                    opt_name = opt.get('name', '').lower()
                    opt_values = opt.get('values', [])
                    if 'color' in opt_name or 'shade' in opt_name:
                        data['shade_count'] = len(opt_values)
                        data['shades'] = opt_values

                return data

        except Exception as e:
            print(f"JSON failed, trying HTML: {e}")

        # Fall back to HTML scraping
        soup = self._get_page(url)
        if not soup:
            return data

        # Basic extraction
        name = soup.find('h1')
        if name:
            data['name'] = name.get_text(strip=True)

        # OG meta tags
        og_desc = soup.find('meta', {'property': 'og:description'})
        if og_desc:
            data['description'] = og_desc.get('content', '')[:2000]

        return data

    def _parse_product_description(self, text: str) -> Dict:
        """Parse structured sections from product description text."""
        sections = {}
        lines = text.split('\n')

        # Section detection patterns
        patterns = {
            'how_to_use': r'^(?:how\s+to\s+use|directions|usage|application)',
            'benefits': r'^(?:benefits|what\s+it\s+does|features)',
            'ingredients': r'^(?:full\s+)?ingredients?(?:\s+list)?',
            'key_ingredients': r'^key\s+ingredients?',
            'size': r'^size',
            'about': r'^about|^description',
        }

        current_section = None
        content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this is a header
            is_header = False
            for section, pattern in patterns.items():
                if re.match(pattern, line.lower()) and len(line) < 40:
                    # Save previous section
                    if current_section and content:
                        sections[current_section] = ' '.join(content)[:1500]
                    current_section = section
                    content = []
                    is_header = True
                    break

            if not is_header and current_section:
                content.append(line)

        # Save last section
        if current_section and content:
            sections[current_section] = ' '.join(content)[:1500]

        return sections

    def _extract_ingredients(self, text: str) -> str:
        """Extract ingredient list from text."""
        # Look for ingredient section
        patterns = [
            r'(?:full\s+)?ingredients?\s*[:\-]?\s*(.+?)(?:\n\n|\Z)',
            r'ingredients?\s+list\s*[:\-]?\s*(.+?)(?:\n\n|\Z)',
        ]

        text_lower = text.lower()

        for pattern in patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL)
            if match:
                ingredients = match.group(1)
                # Clean up
                ingredients = re.sub(r'\s+', ' ', ingredients).strip()
                # Check if it looks like an ingredient list
                if ',' in ingredients and len(ingredients) > 50:
                    return ingredients[:2000]

        return ''


def detect_source(url: str) -> str:
    """Detect the source type from URL."""
    domain = urlparse(url).netloc.lower()

    if 'sephora.com' in domain:
        return 'sephora'
    elif 'credobeauty.com' in domain or 'credo' in domain:
        return 'credo'
    else:
        return 'shopify'  # Default to Shopify for brand sites


def scrape_product(url: str) -> Dict:
    """Scrape product from any supported source."""
    source = detect_source(url)

    if source == 'sephora':
        scraper = SephoraScraper()
    elif source == 'credo':
        scraper = CredoBeautyScraper()
    else:
        scraper = ShopifyBrandScraper()

    return scraper.scrape_product(url)


def main():
    parser = argparse.ArgumentParser(description='Scrape product data from retailers')
    parser.add_argument('url', nargs='?', help='Product URL to scrape')
    parser.add_argument('--output', '-o', help='Output JSON file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    if not args.url:
        parser.print_help()
        print("\nExamples:")
        print('  python scrape_retailer_data.py "https://www.sephora.com/product/..."')
        print('  python scrape_retailer_data.py "https://credobeauty.com/products/..."')
        print('  python scrape_retailer_data.py "https://tower28beauty.com/products/..."')
        return

    print(f"Scraping: {args.url}")
    print(f"Detected source: {detect_source(args.url)}")

    data = scrape_product(args.url)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved to: {args.output}")
    else:
        print("\n" + "=" * 60)
        print("SCRAPED DATA")
        print("=" * 60)
        for key, value in data.items():
            if isinstance(value, list):
                print(f"\n{key}:")
                for item in value[:5]:
                    print(f"  - {item}")
                if len(value) > 5:
                    print(f"  ... and {len(value) - 5} more")
            elif isinstance(value, str) and len(value) > 100:
                print(f"\n{key}:\n  {value[:200]}...")
            else:
                print(f"{key}: {value}")


if __name__ == '__main__':
    main()
