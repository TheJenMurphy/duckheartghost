#!/usr/bin/env python3
"""
Scrape product images from Credo Beauty for matched products.
Uses the Credo URLs from sync_credo_products.py output.

Usage:
    python scrape_credo_images.py --collection makeups --dry-run
    python scrape_credo_images.py --collection skincares --live
"""

import os
import sys
import time
import re
import json
import random
from pathlib import Path
from typing import Dict, List, Optional

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

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

IMAGE_FIELDS = [
    'gallery-image-10',  # Hero image
    'image-2', 'image-3', 'image-4', 'image-5',
    'image-6', 'image-7', 'image-8', 'image-9', 'image-10',
    'image-11', 'image-12', 'image-13', 'image-14', 'image-15',
]


def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }


def get_credo_product_images(credo_slug: str) -> List[str]:
    """Get images from a Credo product page."""
    product_url = f"https://credobeauty.com/products/{credo_slug}"
    images = []

    # Try Shopify JSON endpoint first
    json_url = f"{product_url}.json"
    try:
        resp = requests.get(json_url, headers=get_random_headers(), timeout=15)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get('Retry-After', 30))
            print(f"  Rate limited, waiting {retry_after}s...", end=" ", flush=True)
            time.sleep(retry_after)
            resp = requests.get(json_url, headers=get_random_headers(), timeout=15)

        if resp.ok:
            data = resp.json()
            product = data.get('product', {})
            img_list = product.get('images', [])
            images = [img.get('src', '') for img in img_list if img.get('src')]
            if images:
                return images[:15]

    except (json.JSONDecodeError, requests.RequestException) as e:
        pass

    # Fallback to HTML parsing
    time.sleep(1)
    try:
        resp = requests.get(product_url, headers=get_random_headers(), timeout=15)

        if resp.status_code == 429:
            time.sleep(30)
            resp = requests.get(product_url, headers=get_random_headers(), timeout=15)

        if not resp.ok:
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Get og:image
        og = soup.find('meta', property='og:image')
        if og and og.get('content'):
            images.append(og['content'])

        # Get gallery images
        for img in soup.select('.product__media img, .product-gallery img, [data-product-media] img'):
            src = img.get('src') or img.get('data-src')
            if src and src not in images:
                if not src.startswith('http'):
                    src = f"https://credobeauty.com{src}"
                images.append(src)

    except requests.RequestException:
        pass

    return images[:15]


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
    """Scrape Credo images for products in collection."""
    collection_id = COLLECTIONS.get(collection_name)
    if not collection_id:
        print(f"Unknown collection: {collection_name}")
        return

    # Load sync data to get Credo URLs
    sync_file = Path(__file__).parent / f'credo_sync_{collection_name}.json'
    if not sync_file.exists():
        print(f"Sync file not found: {sync_file}")
        print("Run sync_credo_products.py first")
        return

    with open(sync_file) as f:
        sync_data = json.load(f)

    credo_products = {p['id']: p for p in sync_data.get('on_credo', [])}
    print(f"Loaded {len(credo_products)} Credo-matched products from sync file", flush=True)

    print(f"\n{'='*70}", flush=True)
    print(f"SCRAPING CREDO IMAGES: {collection_name.upper()}", flush=True)
    print(f"{'='*70}", flush=True)

    # Get current Webflow items
    items = client.get_items(collection_id)
    print(f"Loaded {len(items)} items from Webflow", flush=True)

    # Find items that need images and are on Credo
    needs_images = []
    for item in items:
        item_id = item['id']
        if item_id not in credo_products:
            continue

        fd = item.get('fieldData', {})
        hero = fd.get('gallery-image-10', {})
        has_hero = bool(hero and hero.get('url'))

        if not has_hero:
            needs_images.append({
                'item': item,
                'credo_slug': credo_products[item_id]['credo_slug']
            })

    print(f"Products needing images: {len(needs_images)}", flush=True)

    if limit > 0:
        needs_images = needs_images[:limit]
        print(f"Processing first {limit} items", flush=True)

    updated = 0
    found = 0

    for i, data in enumerate(needs_images, 1):
        item = data['item']
        credo_slug = data['credo_slug']
        item_id = item['id']
        fd = item.get('fieldData', {})
        name = fd.get('name', 'Unknown')

        print(f"[{i}/{len(needs_images)}] {name[:45]}...", end=" ", flush=True)

        # Get images from Credo
        images = get_credo_product_images(credo_slug)

        if images:
            print(f"Found {len(images)} images", flush=True)
            found += 1

            if not dry_run:
                # Prepare field data
                field_data = {}
                for j, img_url in enumerate(images[:len(IMAGE_FIELDS)]):
                    field_name = IMAGE_FIELDS[j]
                    field_data[field_name] = {'url': img_url}

                if client.update_item(collection_id, item_id, name, field_data):
                    updated += 1
                time.sleep(0.5)
        else:
            print("No images found", flush=True)

        # Rate limiting for Credo
        time.sleep(2)

    print(f"\n{'='*70}", flush=True)
    print(f"Products with images found: {found}", flush=True)
    print(f"{'Updated' if not dry_run else 'Would update'}: {updated}", flush=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape images from Credo Beauty")
    parser.add_argument("--collection", default="makeups", help="Collection name")
    parser.add_argument("--limit", type=int, default=0, help="Limit items")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.live:
        print("Specify --dry-run or --live")
        return

    dry_run = not args.live

    print("=" * 70, flush=True)
    print("CREDO IMAGE SCRAPER", flush=True)
    print("=" * 70, flush=True)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}", flush=True)

    client = WebflowClient()
    process_collection(client, args.collection, dry_run, args.limit)

    print("\nDone!", flush=True)


if __name__ == "__main__":
    main()
