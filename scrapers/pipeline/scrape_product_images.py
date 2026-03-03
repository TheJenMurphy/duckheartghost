#!/usr/bin/env python3
"""
Scrape product gallery images from brand websites.

Updates up to 15 single image fields:
- gallery-image-10 (hero)
- image-2 through image-15

Supports:
- Shopify stores (most clean beauty brands)
- Direct image extraction from product pages

Usage:
    python scrape_product_images.py --collection makeups --dry-run
    python scrape_product_images.py --collection skincares --live --limit 20
"""

import os
import sys
import time
import re
import json
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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

# 15 single image fields (workaround for MultiImage API limitation)
IMAGE_FIELDS = [
    'gallery-image-10',  # Hero image
    'image-2',
    'image-3',
    'image-4',
    'image-5',
    'image-6',
    'image-7',
    'image-8',
    'image-9',
    'image-10',
    'image-11',
    'image-12',
    'image-13',
    'image-14',
    'image-15',
]


def classify_product_image(url: str, alt: str = '') -> str:
    """Classify product image type based on URL and alt text."""
    url_lower = url.lower()
    alt_lower = alt.lower() if alt else ''
    combined = url_lower + ' ' + alt_lower

    # Hero/product shot indicators (white/transparent background)
    hero_patterns = ['hero', 'main', 'primary', 'pdp', 'product-shot', 'packshot',
                     'front', 'white', 'transparent', 'clean', 'studio', '_1.', '_01.']
    for pattern in hero_patterns:
        if pattern in combined:
            return 'hero'

    # Model/lifestyle images
    model_patterns = ['model', 'lifestyle', 'look', 'worn', 'wearing', 'face',
                      'application', 'before-after', 'result', 'skin']
    for pattern in model_patterns:
        if pattern in combined:
            return 'model'

    # Swatch images
    swatch_patterns = ['swatch', 'shade', 'color', 'texture', 'pigment', 'arm']
    for pattern in swatch_patterns:
        if pattern in combined:
            return 'swatch'

    # Infographic/detail images
    info_patterns = ['info', 'ingredient', 'benefit', 'how-to', 'detail', 'zoom',
                     'closeup', 'close-up', 'text', 'diagram']
    for pattern in info_patterns:
        if pattern in combined:
            return 'info'

    # Color variant detection (to filter duplicates)
    variant_patterns = ['-shade-', '-color-', '-tone-', 'variant', '_v1', '_v2', '_v3']
    for pattern in variant_patterns:
        if pattern in combined:
            return 'variant'

    return 'other'


def dedupe_color_variants(images: List[dict]) -> List[dict]:
    """Remove duplicate color variants, keeping one per base image."""
    seen_bases = set()
    unique_images = []

    for img in images:
        url = img.get('url', '')
        # Extract base image name (remove color/shade suffixes)
        base = re.sub(r'[-_](shade|color|tone|variant|v\d+)[-_]?\w*', '', url.lower())
        base = re.sub(r'[-_]\d{1,2}\.', '.', base)  # Remove _1. _2. etc.

        if base not in seen_bases:
            seen_bases.add(base)
            unique_images.append(img)

    return unique_images


def select_best_product_images(images: List[str], max_count: int = 15) -> List[str]:
    """Select best product images in priority order, avoiding color duplicates."""
    classified = {'hero': [], 'model': [], 'swatch': [], 'info': [], 'variant': [], 'other': []}

    for url in images:
        img_type = classify_product_image(url)
        classified[img_type].append({'url': url, 'type': img_type})

    # Dedupe variants
    for category in classified:
        classified[category] = dedupe_color_variants(classified[category])

    # Build final list in priority order
    result = []

    # 1. Hero images first (white/transparent background)
    for img in classified['hero'][:2]:
        result.append(img['url'])

    # 2. Model/lifestyle images
    for img in classified['model'][:4]:
        result.append(img['url'])

    # 3. Swatch images (just 1-2)
    for img in classified['swatch'][:2]:
        result.append(img['url'])

    # 4. Info/detail images
    for img in classified['info'][:3]:
        result.append(img['url'])

    # 5. Other images to fill remaining slots
    for img in classified['other']:
        if len(result) >= max_count:
            break
        if img['url'] not in result:
            result.append(img['url'])

    # 6. If still need more, add some variants
    for img in classified['variant']:
        if len(result) >= max_count:
            break
        if img['url'] not in result:
            result.append(img['url'])

    return result[:max_count]


def get_shopify_images(url: str) -> List[str]:
    """Extract images from a Shopify product page."""
    try:
        # Try the .json endpoint first
        json_url = url.rstrip('/') + '.json'
        resp = requests.get(json_url, headers=HEADERS, timeout=15)

        if resp.ok:
            data = resp.json()
            product = data.get('product', {})
            images = product.get('images', [])
            raw_urls = [img.get('src', '') for img in images if img.get('src')]
            # Apply smart selection
            return select_best_product_images(raw_urls)

    except (json.JSONDecodeError, requests.RequestException):
        pass

    # Fallback to HTML parsing
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if not resp.ok:
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Look for product images in various patterns
        images = []

        # Pattern 1: og:image meta tag
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            images.append(og_image['content'])

        # Pattern 2: Product gallery images
        for img in soup.select('.product__media img, .product-single__photo img, [data-product-image] img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src:
                # Convert to full size
                src = re.sub(r'_\d+x\d*\.', '_1200x.', src)
                if not src.startswith('http'):
                    src = urljoin(url, src)
                images.append(src)

        # Pattern 3: Look for srcset
        for img in soup.find_all('img'):
            srcset = img.get('srcset', '')
            if srcset:
                # Get the largest image from srcset
                parts = srcset.split(',')
                for part in reversed(parts):
                    if 'http' in part:
                        src = re.search(r'(https?://[^\s]+)', part)
                        if src:
                            images.append(src.group(1))
                            break

        return list(dict.fromkeys(images))[:15]  # Dedupe and limit

    except requests.RequestException:
        return []


def search_credo_beauty(product_name: str) -> List[str]:
    """Search Credo Beauty for product images."""
    try:
        # Clean product name for search
        search_term = re.sub(r'[^\w\s]', '', product_name).strip()
        search_url = f"https://credobeauty.com/search?q={search_term.replace(' ', '+')}"

        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        if not resp.ok:
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Look for product links in search results
        product_link = soup.select_one('.product-card a, .product-item a, [data-product-id] a')
        if product_link:
            product_url = product_link.get('href', '')
            if product_url and not product_url.startswith('http'):
                product_url = f"https://credobeauty.com{product_url}"
            if product_url:
                return get_shopify_images(product_url)

    except requests.RequestException:
        pass

    return []


def search_sephora(product_name: str) -> List[str]:
    """Search Sephora for product images."""
    try:
        # Clean product name for search
        search_term = re.sub(r'[^\w\s]', '', product_name).strip()
        search_url = f"https://www.sephora.com/search?keyword={search_term.replace(' ', '%20')}"

        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        if not resp.ok:
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        images = []

        # Look for product images in search results
        for img in soup.select('.css-klx76, [data-comp="ProductTile"] img, .ProductTile img'):
            src = img.get('src') or img.get('data-src')
            if src and 'sephora' in src:
                # Get higher resolution version
                src = re.sub(r'_\d+x\d+', '_500x500', src)
                images.append(src)

        return images[:5]  # Limit to 5 from search

    except requests.RequestException:
        pass

    return []


def get_images_from_url(url: str) -> List[str]:
    """Get images from any product URL."""
    if not url:
        return []

    # Detect Shopify
    if any(x in url for x in ['/products/', 'myshopify.com', 'shopify']):
        return get_shopify_images(url)

    # Generic extraction - more aggressive approach
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if not resp.ok:
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        images = []

        # Get og:image first (usually the hero)
        og = soup.find('meta', property='og:image')
        if og and og.get('content'):
            images.append(og['content'])

        # Look for product gallery containers (common patterns)
        gallery_selectors = [
            '.product-gallery img',
            '.product-images img',
            '.product-media img',
            '.pdp-gallery img',
            '.product__images img',
            '[data-gallery] img',
            '.swiper-slide img',
            '.carousel-item img',
            '.slick-slide img',
        ]

        for selector in gallery_selectors:
            for img in soup.select(selector):
                src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                if src and src not in images:
                    if not src.startswith('http'):
                        src = urljoin(url, src)
                    # Skip tiny/icon images
                    if not any(x in src.lower() for x in ['icon', 'logo', 'badge', '1x1', 'pixel', 'svg']):
                        images.append(src)

        # Fallback: look for any large product images
        if len(images) < 3:
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src', '')
                if not src or src in images:
                    continue

                # Skip tiny images, icons, logos
                if any(x in src.lower() for x in ['icon', 'logo', 'badge', 'payment', '1x1', 'pixel', 'svg', 'sprite']):
                    continue

                # Look for product-related images by class/alt
                alt = (img.get('alt', '') or '').lower()
                classes = ' '.join(img.get('class', []) if img.get('class') else [])
                parent_classes = ' '.join(img.parent.get('class', []) if img.parent and img.parent.get('class') else [])

                if any(x in (classes + alt + parent_classes).lower() for x in ['product', 'gallery', 'main', 'hero', 'pdp', 'zoom']):
                    if not src.startswith('http'):
                        src = urljoin(url, src)
                    images.append(src)

        return list(dict.fromkeys(images))[:15]

    except requests.RequestException:
        return []


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

    def update_item(self, collection_id: str, item_id: str, field_data: Dict) -> bool:
        url = f'{WEBFLOW_API_BASE}/collections/{collection_id}/items/{item_id}'

        payload = {
            'isArchived': False,
            'isDraft': False,
            'fieldData': field_data
        }

        resp = self.session.patch(url, json=payload, headers={'Content-Type': 'application/json'})

        if resp.status_code == 429:
            time.sleep(int(resp.headers.get('Retry-After', 60)))
            return self.update_item(collection_id, item_id, field_data)

        return resp.ok


def process_collection(client: WebflowClient, collection_name: str, dry_run: bool = True, limit: int = 0):
    """Process a collection to fill images."""
    collection_id = COLLECTIONS.get(collection_name)
    if not collection_id:
        print(f"Unknown collection: {collection_name}")
        return

    print(f"\n{'='*70}")
    print(f"Scraping Images for: {collection_name.upper()}")
    print(f"{'='*70}")
    print(f"Target fields: {', '.join(IMAGE_FIELDS)}")

    items = client.get_items(collection_id)
    print(f"Loaded {len(items)} items")

    # Find items missing any images (hero or gallery) or missing new slots
    needs_update = []
    has_hero_needs_gallery = []
    needs_more_images = []

    for item in items:
        fd = item.get('fieldData', {})
        hero = fd.get('gallery-image-10')
        image_2 = fd.get('image-2')
        image_11 = fd.get('image-11')  # Check if new slots are filled
        url = fd.get('external-link')

        if not url:
            continue

        if not hero:
            needs_update.append(item)
        elif not image_2:
            # Has hero but missing gallery images
            has_hero_needs_gallery.append(item)
        elif not image_11 and fd.get('image-10'):
            # Has 10 images but missing new slots 11-15
            needs_more_images.append(item)

    print(f"Items missing hero image: {len(needs_update)}")
    print(f"Items with hero but missing gallery: {len(has_hero_needs_gallery)}")
    print(f"Items with 10 images needing more: {len(needs_more_images)}")

    # Combine lists - prioritize items missing hero, then gallery, then more images
    needs_update = needs_update + has_hero_needs_gallery + needs_more_images
    print(f"Total to process: {len(needs_update)}")

    if limit > 0:
        needs_update = needs_update[:limit]
        print(f"Processing first {limit} items")

    updated = 0
    found = 0
    total_images = 0

    for i, item in enumerate(needs_update, 1):
        item_id = item['id']
        fd = item.get('fieldData', {})
        name = fd.get('name', 'Unknown')
        url = fd.get('external-link', '')

        print(f"[{i}/{len(needs_update)}] {name[:40]}...", end=" ")

        images = get_images_from_url(url)

        # Fallback to Credo Beauty if no images found
        if not images:
            print("trying Credo...", end=" ")
            images = search_credo_beauty(name)

        # Fallback to Sephora if still no images
        if not images:
            print("trying Sephora...", end=" ")
            images = search_sephora(name)

        if images:
            img_count = min(len(images), len(IMAGE_FIELDS))
            print(f"Found {len(images)} images, using {img_count}")
            found += 1
            total_images += img_count

            update_data = {}

            # Fill each image field with a different image
            for idx, field in enumerate(IMAGE_FIELDS):
                if idx < len(images):
                    update_data[field] = {'url': images[idx]}

            if not dry_run and update_data:
                if client.update_item(collection_id, item_id, update_data):
                    updated += 1
                time.sleep(0.5)
            elif update_data:
                updated += 1
        else:
            print("No images found")

        # Rate limiting
        time.sleep(1)

    print(f"\n{'='*70}")
    print(f"Products with images: {found}")
    print(f"Total images scraped: {total_images}")
    print(f"{'Updated' if not dry_run else 'Would update'}: {updated}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape product images")
    parser.add_argument("--collection", default="makeups", help="Collection name")
    parser.add_argument("--limit", type=int, default=0, help="Limit items to process")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.live:
        print("Specify --dry-run or --live")
        return

    dry_run = not args.live

    print("=" * 70)
    print("SCRAPE PRODUCT IMAGES")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")

    client = WebflowClient()
    process_collection(client, args.collection, dry_run, args.limit)

    print("\nDone!")


if __name__ == "__main__":
    main()
