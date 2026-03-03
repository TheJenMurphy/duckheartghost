#!/usr/bin/env python3
"""
Scrape star ratings and review counts from Sephora for products.

Updates: star-rating, review-number

Usage:
    python scrape_sephora_reviews.py --collection makeups --dry-run
    python scrape_sephora_reviews.py --collection skincares --live
"""

import os
import sys
import time
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

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

# User agent for requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


def search_sephora(product_name: str, brand: str = "") -> Optional[Dict]:
    """Search Sephora for a product and return rating data."""
    query = f"{brand} {product_name}".strip()
    search_url = f"https://www.sephora.com/search?keyword={quote_plus(query)}"

    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        if not resp.ok:
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Look for product data in JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    rating = data.get('aggregateRating', {})
                    return {
                        'rating': float(rating.get('ratingValue', 0)),
                        'reviews': int(rating.get('reviewCount', 0)),
                        'source': 'sephora'
                    }
                elif isinstance(data, list):
                    for item in data:
                        if item.get('@type') == 'Product':
                            rating = item.get('aggregateRating', {})
                            return {
                                'rating': float(rating.get('ratingValue', 0)),
                                'reviews': int(rating.get('reviewCount', 0)),
                                'source': 'sephora'
                            }
            except (json.JSONDecodeError, ValueError):
                continue

        # Fallback: look for rating in HTML
        rating_elem = soup.select_one('[data-at="rating"]')
        if rating_elem:
            try:
                rating_text = rating_elem.get_text(strip=True)
                rating = float(re.search(r'[\d.]+', rating_text).group())
                return {'rating': rating, 'reviews': 0, 'source': 'sephora-html'}
            except:
                pass

        return None

    except requests.RequestException as e:
        print(f"  Request error: {e}")
        return None


def search_ulta(product_name: str, brand: str = "") -> Optional[Dict]:
    """Search Ulta for a product and return rating data."""
    query = f"{brand} {product_name}".strip()
    search_url = f"https://www.ulta.com/search?q={quote_plus(query)}"

    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        if not resp.ok:
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Look for rating data
        rating_elem = soup.select_one('.ProductCard__rating')
        if rating_elem:
            try:
                rating_text = rating_elem.get_text(strip=True)
                rating = float(re.search(r'[\d.]+', rating_text).group())

                # Look for review count
                review_elem = soup.select_one('.ProductCard__reviewCount')
                reviews = 0
                if review_elem:
                    review_text = review_elem.get_text(strip=True)
                    match = re.search(r'(\d+)', review_text.replace(',', ''))
                    if match:
                        reviews = int(match.group(1))

                return {'rating': rating, 'reviews': reviews, 'source': 'ulta'}
            except:
                pass

        return None

    except requests.RequestException as e:
        print(f"  Request error: {e}")
        return None


def get_product_ratings(product_name: str, brand: str = "") -> Tuple[float, int]:
    """Try multiple sources to get product ratings."""
    # Try Sephora first
    result = search_sephora(product_name, brand)
    if result and result.get('rating', 0) > 0:
        return result['rating'], result['reviews']

    # Wait before trying Ulta
    time.sleep(1)

    # Try Ulta
    result = search_ulta(product_name, brand)
    if result and result.get('rating', 0) > 0:
        return result['rating'], result['reviews']

    return 0, 0


class WebflowClient:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
        })

    def get_items(self, collection_id: str) -> List[Dict]:
        """Fetch all items from a collection."""
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
        """Update an item's fields."""
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
    """Process a collection to fill star ratings and review counts."""
    collection_id = COLLECTIONS.get(collection_name)
    if not collection_id:
        print(f"Unknown collection: {collection_name}")
        return

    print(f"\n{'='*70}")
    print(f"Scraping Reviews for: {collection_name.upper()}")
    print(f"{'='*70}")

    items = client.get_items(collection_id)
    print(f"Loaded {len(items)} items")

    # Find items missing ratings
    needs_update = []
    for item in items:
        fd = item.get('fieldData', {})
        rating = fd.get('star-rating')
        reviews = fd.get('review-number')

        if not rating or rating == 0:
            needs_update.append(item)

    print(f"Items missing star-rating: {len(needs_update)}")

    if limit > 0:
        needs_update = needs_update[:limit]
        print(f"Processing first {limit} items")

    updated = 0
    found = 0

    for i, item in enumerate(needs_update, 1):
        item_id = item['id']
        fd = item.get('fieldData', {})
        name = fd.get('name', 'Unknown')
        brand = fd.get('brand-name-2', '') or ''

        print(f"[{i}/{len(needs_update)}] {name[:50]}...", end=" ")

        # Search for ratings
        rating, reviews = get_product_ratings(name, brand)

        if rating > 0:
            print(f"Found: {rating:.1f} stars, {reviews} reviews")
            found += 1

            update_data = {'star-rating': rating}
            if reviews > 0:
                update_data['review-number'] = reviews

            if not dry_run:
                if client.update_item(collection_id, item_id, update_data):
                    updated += 1
                time.sleep(0.5)
            else:
                updated += 1
        else:
            print("Not found")

        # Rate limiting for scraping
        time.sleep(2)

    print(f"\n{'='*70}")
    print(f"Found ratings for: {found}")
    print(f"{'Updated' if not dry_run else 'Would update'}: {updated}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape star ratings from retailers")
    parser.add_argument("--collection", default="makeups", help="Collection name")
    parser.add_argument("--limit", type=int, default=0, help="Limit items to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without updating")
    parser.add_argument("--live", action="store_true", help="Actually update Webflow")
    args = parser.parse_args()

    if not args.dry_run and not args.live:
        print("Specify --dry-run or --live")
        return

    dry_run = not args.live

    print("=" * 70)
    print("SCRAPE SEPHORA/ULTA REVIEWS")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")

    client = WebflowClient()
    process_collection(client, args.collection, dry_run, args.limit)

    print("\nDone!")


if __name__ == "__main__":
    main()
