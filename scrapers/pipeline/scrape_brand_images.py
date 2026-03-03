#!/usr/bin/env python3
"""
Scrape product images directly from brand websites.
Uses longer delays and better retry logic to avoid rate limiting.

Usage:
    python scrape_brand_images.py --collection tools --dry-run
    python scrape_brand_images.py --collection skincares --live
"""

import os
import sys
import time
import re
import json
import random
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

import requests
from bs4 import BeautifulSoup

WEBFLOW_API_BASE = "https://api.webflow.com/v2"

COLLECTIONS = {
    "makeups": "697d3803e654519eef084068",
    "skincares": "697d723c3df8451b1f1cce1a",
    "tools": "697d7d4a824e85c10e862dd1",
}

# Multiple user agents to rotate
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

IMAGE_FIELDS = [
    'gallery-image-10',  # Hero image
    'image-2', 'image-3', 'image-4', 'image-5',
    'image-6', 'image-7', 'image-8', 'image-9', 'image-10',
    'image-11', 'image-12', 'image-13', 'image-14', 'image-15',
]


def get_random_headers():
    """Get headers with random user agent."""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }


def fetch_with_retry(url: str, max_retries: int = 3, base_delay: float = 2.0) -> Optional[requests.Response]:
    """Fetch URL with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            # Add jitter to avoid thundering herd
            delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
            if attempt > 0:
                print(f"  Retry {attempt + 1}/{max_retries} after {delay:.1f}s...", end=" ", flush=True)
                time.sleep(delay)

            resp = requests.get(url, headers=get_random_headers(), timeout=20)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get('Retry-After', 30))
                print(f"  Rate limited, waiting {retry_after}s...", end=" ", flush=True)
                time.sleep(retry_after)
                continue

            return resp

        except requests.RequestException as e:
            if attempt == max_retries - 1:
                print(f"  Request failed: {e}", flush=True)

    return None


def scrape_shopify_product(url: str) -> List[str]:
    """Scrape images from a Shopify product page."""
    images = []

    # Try JSON endpoint first
    json_url = url.rstrip('/') + '.json'
    resp = fetch_with_retry(json_url)

    if resp and resp.ok:
        try:
            data = resp.json()
            product = data.get('product', {})
            img_list = product.get('images', [])
            images = [img.get('src', '') for img in img_list if img.get('src')]
            if images:
                return images
        except json.JSONDecodeError:
            pass

    # Fallback to HTML parsing
    time.sleep(1)  # Brief delay between requests
    resp = fetch_with_retry(url)

    if not resp or not resp.ok:
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Try multiple image extraction patterns

    # Pattern 1: Look for product JSON in script tags
    for script in soup.find_all('script', type='application/json'):
        try:
            data = json.loads(script.string or '{}')
            # Check for product data
            if 'product' in data:
                img_list = data['product'].get('images', [])
                for img in img_list:
                    src = img.get('src') or img.get('url') or ''
                    if src and src not in images:
                        images.append(src)
        except (json.JSONDecodeError, TypeError):
            pass

    # Pattern 2: Look for product images in data attributes
    for el in soup.select('[data-product-featured-image], [data-product-image], [data-image]'):
        src = el.get('src') or el.get('data-src') or el.get('data-zoom-image')
        if src and src not in images:
            if not src.startswith('http'):
                src = urljoin(url, src)
            images.append(src)

    # Pattern 3: Look for og:image meta tag
    og_img = soup.find('meta', property='og:image')
    if og_img and og_img.get('content'):
        src = og_img['content']
        if src and src not in images:
            images.insert(0, src)  # Hero image first

    # Pattern 4: Product gallery images
    for img in soup.select('.product__media img, .product-single__photos img, .product-images img, .product-gallery img'):
        src = img.get('src') or img.get('data-src')
        if src and 'placeholder' not in src.lower() and src not in images:
            if not src.startswith('http'):
                src = urljoin(url, src)
            images.append(src)

    # Pattern 5: Look for srcset with high-res images
    for img in soup.find_all('img', srcset=True):
        srcset = img.get('srcset', '')
        # Parse srcset to get highest resolution
        parts = srcset.split(',')
        for part in parts:
            src = part.strip().split()[0]
            if src and 'placeholder' not in src.lower() and src not in images:
                if not src.startswith('http'):
                    src = urljoin(url, src)
                images.append(src)
                break  # Just get one from srcset

    return images


def clean_image_url(url: str) -> str:
    """Clean and normalize image URL."""
    if not url:
        return ''

    # Remove query params except for Shopify CDN
    if 'shopify' in url or 'cdn.shopify' in url:
        # Keep Shopify CDN structure but request larger size
        url = re.sub(r'_\d+x\d*\.', '_1000x.', url)
        url = re.sub(r'\?v=\d+', '', url)

    return url


class WebflowClient:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
        })

    def get_items(self, collection_id: str) -> List[Dict]:
        items = []
        offset = 0

        while True:
            url = f'{WEBFLOW_API_BASE}/collections/{collection_id}/items?limit=100&offset={offset}'
            resp = self.session.get(url)

            if resp.status_code == 429:
                time.sleep(int(resp.headers.get('Retry-After', 60)))
                continue

            if not resp.ok:
                break

            data = resp.json()
            batch = data.get('items', [])
            items.extend(batch)

            if len(batch) < 100:
                break
            offset += 100
            time.sleep(0.5)

        return items

    def update_item(self, collection_id: str, item_id: str, item_name: str, field_data: Dict) -> bool:
        url = f'{WEBFLOW_API_BASE}/collections/{collection_id}/items/{item_id}'

        field_data['name'] = item_name

        payload = {
            'isArchived': False,
            'isDraft': False,
            'fieldData': field_data
        }

        resp = self.session.patch(url, json=payload, headers={'Content-Type': 'application/json'})

        if resp.status_code == 429:
            time.sleep(int(resp.headers.get('Retry-After', 60)))
            return self.update_item(collection_id, item_id, item_name, field_data)

        if not resp.ok:
            print(f" Error {resp.status_code}: {resp.text[:200]}", flush=True)

        return resp.ok


def process_collection(client: WebflowClient, collection_name: str, dry_run: bool = True, limit: int = 0):
    """Process a collection to scrape product images."""
    collection_id = COLLECTIONS.get(collection_name)
    if not collection_id:
        print(f"Unknown collection: {collection_name}")
        return

    print(f"\n{'='*70}", flush=True)
    print(f"SCRAPING IMAGES FROM BRAND WEBSITES: {collection_name.upper()}", flush=True)
    print(f"{'='*70}", flush=True)

    items = client.get_items(collection_id)
    print(f"Loaded {len(items)} items", flush=True)

    # Find items missing hero image that have external links
    needs_update = []
    for item in items:
        fd = item.get('fieldData', {})
        hero = fd.get('gallery-image-10', {})
        has_hero = bool(hero and hero.get('url'))
        ext_link = fd.get('external-link', '')

        if not has_hero and ext_link:
            needs_update.append(item)

    print(f"Items missing images with source URLs: {len(needs_update)}", flush=True)

    if limit > 0:
        needs_update = needs_update[:limit]
        print(f"Processing first {limit} items", flush=True)

    updated = 0
    found = 0

    # Group by domain to batch requests and respect rate limits
    by_domain = {}
    for item in needs_update:
        fd = item.get('fieldData', {})
        url = fd.get('external-link', '')
        domain = urlparse(url).netloc
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(item)

    print(f"Domains to scrape: {', '.join(by_domain.keys())}", flush=True)
    print()

    item_num = 0
    for domain, domain_items in by_domain.items():
        print(f"--- {domain} ({len(domain_items)} products) ---", flush=True)

        for item in domain_items:
            item_num += 1
            item_id = item['id']
            fd = item.get('fieldData', {})
            name = fd.get('name', 'Unknown')
            url = fd.get('external-link', '')

            print(f"[{item_num}/{len(needs_update)}] {name[:45]}...", end=" ", flush=True)

            # Scrape images from brand website
            images = scrape_shopify_product(url)

            if images:
                # Clean URLs
                images = [clean_image_url(img) for img in images if img]
                images = [img for img in images if img]  # Remove empty

                print(f"Found {len(images)} images", flush=True)
                found += 1

                if not dry_run and images:
                    # Prepare field data for update
                    field_data = {}
                    for i, img_url in enumerate(images[:len(IMAGE_FIELDS)]):
                        field_name = IMAGE_FIELDS[i]
                        field_data[field_name] = {'url': img_url}

                    if client.update_item(collection_id, item_id, name, field_data):
                        updated += 1
                    time.sleep(0.5)  # Rate limit Webflow API
            else:
                print("No images found", flush=True)

            # Delay between product requests (longer delay to avoid rate limits)
            time.sleep(3)

        # Extra delay between domains
        print(f"Waiting before next domain...", flush=True)
        time.sleep(5)

    print(f"\n{'='*70}", flush=True)
    print(f"Products with images found: {found}", flush=True)
    print(f"{'Updated' if not dry_run else 'Would update'}: {updated}", flush=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape product images from brand websites")
    parser.add_argument("--collection", default="tools", help="Collection name")
    parser.add_argument("--limit", type=int, default=0, help="Limit items to process")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.live:
        print("Specify --dry-run or --live")
        return

    dry_run = not args.live

    print("=" * 70, flush=True)
    print("BRAND WEBSITE IMAGE SCRAPER", flush=True)
    print("=" * 70, flush=True)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}", flush=True)

    client = WebflowClient()
    process_collection(client, args.collection, dry_run, args.limit)

    print("\nDone!", flush=True)


if __name__ == "__main__":
    main()
