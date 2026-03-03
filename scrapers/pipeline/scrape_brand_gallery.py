#!/usr/bin/env python3
"""
Scrape full product line images from brand websites for the gallery-2 (MultiImage) field.

For Shopify brands:
  1. Fetch /products.json (all pages) to get every product's hero image
  2. Dedupe by product_type to ensure variety across the full line

For non-Shopify brands:
  1. Scrape homepage for product/collection images
  2. Look for collection/category landing pages and scrape those too

Pushes up to 12 images per brand into the gallery-2 MultiImage field.

Usage:
    PYTHONUNBUFFERED=1 python3 scrape_brand_gallery.py --dry-run
    PYTHONUNBUFFERED=1 python3 scrape_brand_gallery.py --live
    PYTHONUNBUFFERED=1 python3 scrape_brand_gallery.py --dry-run --limit 5 --verbose
    PYTHONUNBUFFERED=1 python3 scrape_brand_gallery.py --live --only-missing
"""

import os
import sys
import time
import json
import random
import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

import requests
from bs4 import BeautifulSoup

WEBFLOW_API_BASE = "https://api.webflow.com/v2"
BRANDS_COLLECTION_ID = "697d981be773ae7dbfc093ed"

MAX_GALLERY_IMAGES = 12

# Image URL patterns to skip
SKIP_IMAGE_PATTERNS = [
    'logo', 'icon', 'badge', 'payment', 'sprite', 'spacer',
    'placeholder', 'blank', 'pixel', 'tracking', 'social',
    'facebook', 'twitter', 'instagram', 'pinterest', 'tiktok',
    'youtube', 'linkedin', 'whatsapp', 'telegram',
    'visa', 'mastercard', 'amex', 'paypal', 'apple-pay',
    'google-pay', 'shopify-pay', 'klarna', 'afterpay',
    'sezzle', 'zip-pay', 'affirm',
    'stars', 'rating', 'review', 'trust', 'seal',
    'arrow', 'chevron', 'caret', 'close', 'menu', 'hamburger',
    'search', 'cart', 'bag', 'wishlist', 'heart',
    'loader', 'spinner', 'loading',
]

PRESS_LOGO_KEYWORDS = [
    'bazaar', 'harpers-bazaar', 'allure', 'vogue', 'glamour',
    'cosmopolitan', 'cosmo', 'instyle', 'refinery29', 'byrdie',
    'teen-vogue', 'nylon', 'bustle', 'popsugar', 'gq', 'esquire',
    'vanity-fair', 'marie-claire', 'self-magazine', 'today-show',
    'good-morning', 'oprah', 'forbes', 'nytimes', 'new-york-times',
    'wall-street', 'wsj', 'cnn', 'bbc', 'people-magazine',
    'womens-health', 'mens-health', 'well-good', 'well-and-good',
    'goop-logo', 'sephora-logo', 'nordstrom-logo', 'ulta-logo',
    'who-what-wear', 'coveteur', 'editorialist', 'the-cut',
    'fashionista', 'glossy', 'beauty-independent', 'wwd', 'womens-wear',
]

# Known brand websites fallback
BRAND_WEBSITES = {
    "kosas": "https://kosas.com",
    "ilia": "https://iliabeauty.com",
    "ilia-beauty": "https://iliabeauty.com",
    "tower-28": "https://tower28beauty.com",
    "tower28": "https://tower28beauty.com",
    "tower-28-beauty": "https://tower28beauty.com",
    "saie": "https://saiehello.com",
    "merit": "https://meritbeauty.com",
    "rare-beauty": "https://rarebeauty.com",
    "fenty": "https://fentybeauty.com",
    "fenty-beauty": "https://fentybeauty.com",
    "glossier": "https://glossier.com",
    "milk-makeup": "https://milkmakeup.com",
    "westman-atelier": "https://westman-atelier.com",
    "rose-inc": "https://roseinc.com",
    "jones-road": "https://jonesroadbeauty.com",
    "kjaer-weis": "https://kjaerweis.com",
    "rms-beauty": "https://rmsbeauty.com",
    "lawless": "https://lawlessbeauty.com",
    "refy": "https://refybeauty.com",
    "patrick-ta": "https://patrickta.com",
    "danessa-myricks": "https://danessamyricksbeauty.com",
    "hourglass": "https://hourglasscosmetics.com",
    "nars": "https://narscosmetics.com",
    "charlotte-tilbury": "https://charlottetilbury.com",
    "mac": "https://maccosmetics.com",
    "lys-beauty": "https://lysbeauty.com",
    "ecotools": "https://ecotools.com",
    "real-techniques": "https://realtechniques.com",
    "vapour-beauty": "https://vapourbeauty.com",
    "w3ll-people": "https://w3llpeople.com",
    "ere-perez": "https://ereperez.com",
    "juice-beauty": "https://juicebeauty.com",
    "100-pure": "https://100percentpure.com",
    "axiology": "https://axiologybeauty.com",
    "elate-cosmetics": "https://elatebeauty.com",
    "antonym-cosmetics": "https://antonymcosmetics.com",
    "alima-pure": "https://alimapure.com",
    "au-naturale": "https://aunaturalecosmetics.com",
    "osea": "https://oseamalibu.com",
    "tata-harper": "https://tataharperskincare.com",
    "herbivore-botanicals": "https://herbivorebotanicals.com",
    "biossance": "https://biossance.com",
}

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }


def fetch_with_retry(url: str, max_retries: int = 3, base_delay: float = 2.0,
                     accept_json: bool = False) -> Optional[requests.Response]:
    headers = get_random_headers()
    if accept_json:
        headers['Accept'] = 'application/json'
    for attempt in range(max_retries):
        try:
            delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
            if attempt > 0:
                print(f"    Retry {attempt + 1}/{max_retries} after {delay:.1f}s...", flush=True)
                time.sleep(delay)
            resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get('Retry-After', 30))
                print(f"    Rate limited, waiting {retry_after}s...", flush=True)
                time.sleep(retry_after)
                continue
            return resp
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                print(f"    Request failed: {e}", flush=True)
    return None


def is_svg(url: str) -> bool:
    return '.svg' in urlparse(url).path.lower() or url.strip().startswith('data:image/svg')


def is_press_logo(url: str) -> bool:
    path = urlparse(url).path
    filename = path.rsplit('/', 1)[-1] if '/' in path else path
    filename = filename.lower().replace('%20', '-').replace('+', '-').replace('_', '-')
    for keyword in PRESS_LOGO_KEYWORDS:
        if keyword in filename:
            return True
    return False


def is_skip_image(url: str) -> bool:
    path = urlparse(url).path.lower()
    filename = path.rsplit('/', 1)[-1] if '/' in path else path
    filename = filename.replace('%20', '-').replace('+', '-').replace('_', '-')
    for pattern in SKIP_IMAGE_PATTERNS:
        if pattern in filename:
            return True
    return is_press_logo(url)


def is_valid_image_url(url: str) -> bool:
    if not url or not url.startswith('http'):
        return False
    try:
        resp = requests.head(url, headers=get_random_headers(), timeout=10, allow_redirects=True)
        ct = resp.headers.get('Content-Type', '')
        return resp.ok and 'image/' in ct
    except requests.RequestException:
        return False


def normalize_shopify_cdn_url(url: str, width: int = 600) -> str:
    if 'cdn.shopify.com' not in url:
        return url
    url = re.sub(r'_(\d+x\d*|\d*x\d+|small|medium|large|grande|master|compact|pico|icon)\.', '.', url)
    url = re.sub(r'\.([a-zA-Z]{3,4})(\?|$)', rf'_{width}x.\1\2', url)
    url = re.sub(r'\?v=\d+', '', url)
    return url


def make_absolute(src: str, base_url: str) -> str:
    if not src or src.startswith('data:'):
        return ''
    if not src.startswith('http'):
        return urljoin(base_url, src)
    return src


def load_brands_json() -> Dict[str, str]:
    brands_path = Path(__file__).parent.parent / 'brands.json'
    if not brands_path.exists():
        return {}
    try:
        data = json.loads(brands_path.read_text())
        mapping = {}
        for brand in data.get('brands', []):
            slug = brand.get('slug', '')
            domain = brand.get('shopify_domain', '')
            if slug and domain:
                if not domain.startswith('http'):
                    domain = f'https://{domain}'
                mapping[slug] = domain
        return mapping
    except (json.JSONDecodeError, KeyError):
        return {}


def resolve_brand_url(slug: str, cms_external_link: str, shopify_map: Dict[str, str]) -> Optional[str]:
    if cms_external_link:
        parsed = urlparse(cms_external_link)
        domain = parsed.netloc.lower().replace('www.', '')
        if 'credo' not in domain and 'credobeauty' not in domain:
            return cms_external_link
    if slug in shopify_map:
        return shopify_map[slug]
    if slug in BRAND_WEBSITES:
        return BRAND_WEBSITES[slug]
    return None


# ---------------------------------------------------------------------------
# Shopify product line scraping — get hero image from every product
# ---------------------------------------------------------------------------

def scrape_shopify_product_line(brand_url: str, verbose: bool = False) -> List[str]:
    """
    Fetch all products from Shopify /products.json and collect hero images.
    Prioritizes variety: takes one product per product_type first, then fills
    remaining slots with additional products.
    Returns up to MAX_GALLERY_IMAGES image URLs.
    """
    parsed = urlparse(brand_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    # Test if Shopify
    test_url = f"{base}/products.json?limit=1"
    resp = fetch_with_retry(test_url, accept_json=True)
    if not resp or resp.status_code != 200:
        if verbose:
            print(f"    [Shopify] /products.json not available", flush=True)
        return []

    try:
        data = resp.json()
        if 'products' not in data:
            return []
    except (json.JSONDecodeError, ValueError):
        return []

    if verbose:
        print(f"    [Shopify] Detected, fetching full product line...", flush=True)

    # Fetch all products (paginated)
    all_products = []
    page = 1
    while True:
        url = f"{base}/products.json?limit=250&page={page}"
        resp = fetch_with_retry(url, accept_json=True)
        if not resp or not resp.ok:
            break
        try:
            data = resp.json()
            batch = data.get('products', [])
            all_products.extend(batch)
            if verbose:
                print(f"    [Shopify] Page {page}: {len(batch)} products (total: {len(all_products)})", flush=True)
            if len(batch) < 250:
                break
            page += 1
            time.sleep(0.5)
        except (json.JSONDecodeError, ValueError):
            break

    if not all_products:
        return []

    # Extract hero images, organized by product_type for variety
    by_type: Dict[str, List[str]] = {}
    for product in all_products:
        product_type = (product.get('product_type') or 'unknown').strip().lower()
        images = product.get('images', [])
        if not images:
            continue
        img_url = images[0].get('src', '')
        if not img_url:
            continue
        img_url = normalize_shopify_cdn_url(img_url)
        if is_svg(img_url) or is_skip_image(img_url):
            continue
        if product_type not in by_type:
            by_type[product_type] = []
        by_type[product_type].append(img_url)

    if verbose:
        print(f"    [Shopify] {len(by_type)} product types found", flush=True)

    # Round-robin across product types for maximum variety
    result = []
    seen = set()
    type_lists = list(by_type.values())

    # Pass 1: one from each type
    for imgs in type_lists:
        for img in imgs:
            if img not in seen:
                result.append(img)
                seen.add(img)
                break
        if len(result) >= MAX_GALLERY_IMAGES:
            break

    # Pass 2: fill remaining with additional products (round-robin)
    if len(result) < MAX_GALLERY_IMAGES:
        idx = 1  # Start at second product in each type
        while len(result) < MAX_GALLERY_IMAGES:
            added = False
            for imgs in type_lists:
                if idx < len(imgs) and imgs[idx] not in seen:
                    result.append(imgs[idx])
                    seen.add(imgs[idx])
                    added = True
                    if len(result) >= MAX_GALLERY_IMAGES:
                        break
            if not added:
                break
            idx += 1

    if verbose:
        for i, url in enumerate(result):
            print(f"    [Shopify] Gallery {i+1}: {url[:70]}", flush=True)

    return result


# ---------------------------------------------------------------------------
# HTML scraping for non-Shopify brands
# ---------------------------------------------------------------------------

def scrape_html_product_images(brand_url: str, verbose: bool = False) -> List[str]:
    """
    Scrape product images from homepage and linked collection pages.
    Returns up to MAX_GALLERY_IMAGES image URLs.
    """
    resp = fetch_with_retry(brand_url)
    if not resp or not resp.ok:
        if verbose:
            print(f"    [HTML] Could not fetch homepage", flush=True)
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    base_url = resp.url
    candidates = []
    seen_urls = set()

    def collect_images_from_soup(s: BeautifulSoup, bu: str, label: str = ""):
        """Extract product-like images from a parsed page."""
        # Strategy A: images in product/collection/featured sections
        section_selectors = [
            '[class*="collection"] img',
            '[class*="category"] img',
            '[class*="featured"] img',
            '[class*="product"] img',
            '[class*="range"] img',
            '[class*="shop"] img',
            '[class*="grid"] img',
            '[class*="card"] img',
            '[id*="collection"] img',
            '[id*="category"] img',
            '[id*="featured"] img',
        ]
        for selector in section_selectors:
            for img in s.select(selector):
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or ''
                src = make_absolute(src, bu)
                if not src or src in seen_urls:
                    continue
                if is_svg(src) or is_skip_image(src):
                    continue
                width = img.get('width', '')
                height = img.get('height', '')
                try:
                    if width and int(width) < 100:
                        continue
                    if height and int(height) < 100:
                        continue
                except (ValueError, TypeError):
                    pass
                seen_urls.add(src)
                candidates.append(src)

        # Strategy B: all larger images
        for img in s.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or ''
            src = make_absolute(src, bu)
            if not src or src in seen_urls:
                continue
            if is_svg(src) or is_skip_image(src):
                continue
            width = img.get('width', '')
            height = img.get('height', '')
            try:
                w = int(width) if width else 0
                h = int(height) if height else 0
                if (w > 0 and w < 150) or (h > 0 and h < 150):
                    continue
            except (ValueError, TypeError):
                pass
            seen_urls.add(src)
            candidates.append(src)

    # Scrape homepage
    collect_images_from_soup(soup, base_url, "homepage")

    # Try to find and scrape collection/shop pages for more images
    if len(candidates) < MAX_GALLERY_IMAGES:
        parsed = urlparse(brand_url)
        shop_keywords = ['collections', 'shop', 'products', 'categories']
        visited = {base_url}
        for a in soup.find_all('a', href=True):
            if len(candidates) >= MAX_GALLERY_IMAGES:
                break
            href = a['href']
            text = (a.get_text(strip=True) or '').lower()
            href_lower = href.lower()
            if any(kw in href_lower or kw in text for kw in shop_keywords):
                full_url = make_absolute(href, base_url)
                if not full_url or full_url in visited:
                    continue
                link_parsed = urlparse(full_url)
                if link_parsed.netloc != parsed.netloc:
                    continue
                visited.add(full_url)
                if verbose:
                    print(f"    [HTML] Following collection link: {full_url[:60]}", flush=True)
                time.sleep(1)
                sub_resp = fetch_with_retry(full_url)
                if sub_resp and sub_resp.ok:
                    sub_soup = BeautifulSoup(sub_resp.text, 'html.parser')
                    collect_images_from_soup(sub_soup, sub_resp.url, "collection")
                if len(visited) >= 4:  # Don't follow too many links
                    break

    # Normalize Shopify CDN URLs if present
    candidates = [normalize_shopify_cdn_url(url) for url in candidates]

    if verbose:
        print(f"    [HTML] Found {len(candidates)} candidate images total", flush=True)

    return candidates[:MAX_GALLERY_IMAGES]


# ---------------------------------------------------------------------------
# Webflow client
# ---------------------------------------------------------------------------

class WebflowClient:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.site_id = os.environ.get('WEBFLOW_SITE_ID', '')
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
                print(f"  Error fetching items: {resp.status_code} {resp.text[:200]}", flush=True)
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
            'fieldData': field_data,
        }
        resp = self.session.patch(url, json=payload, headers={'Content-Type': 'application/json'})
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get('Retry-After', 60)))
            return self.update_item(collection_id, item_id, field_data)
        if not resp.ok:
            print(f"    Update error {resp.status_code}: {resp.text[:200]}", flush=True)
        return resp.ok

    def publish_items(self, collection_id: str, item_ids: List[str]) -> bool:
        if not self.site_id:
            print("  WEBFLOW_SITE_ID not set, skipping publish", flush=True)
            return False
        for i in range(0, len(item_ids), 100):
            batch = item_ids[i:i + 100]
            url = f'{WEBFLOW_API_BASE}/collections/{collection_id}/items/publish'
            resp = self.session.post(url, json={'itemIds': batch},
                                     headers={'Content-Type': 'application/json'})
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get('Retry-After', 60)))
                resp = self.session.post(url, json={'itemIds': batch},
                                         headers={'Content-Type': 'application/json'})
            if not resp.ok:
                print(f"    Publish error (batch {i // 100 + 1}): {resp.status_code} {resp.text[:200]}", flush=True)
                return False
            print(f"  Published batch {i // 100 + 1} ({len(batch)} items)", flush=True)
            time.sleep(1.0)
        return True


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def scrape_gallery_images(brand_url: str, verbose: bool = False) -> List[str]:
    """
    Get up to MAX_GALLERY_IMAGES product line images.
    Tries Shopify API first, falls back to HTML scraping.
    """
    # Try Shopify first
    images = scrape_shopify_product_line(brand_url, verbose=verbose)

    # Fall back to HTML scraping
    if len(images) < 2:
        time.sleep(0.5)
        html_images = scrape_html_product_images(brand_url, verbose=verbose)
        existing = set(images)
        for img in html_images:
            if img not in existing:
                images.append(img)
                existing.add(img)
            if len(images) >= MAX_GALLERY_IMAGES:
                break

    return images[:MAX_GALLERY_IMAGES]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape brand product line images for gallery-2")
    parser.add_argument("--dry-run", action="store_true", help="Preview without updating Webflow")
    parser.add_argument("--live", action="store_true", help="Actually update Webflow")
    parser.add_argument("--only-missing", action="store_true", help="Only brands missing gallery images")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of brands")
    parser.add_argument("--verbose", action="store_true", help="Show detailed scraping info")
    args = parser.parse_args()

    if not args.dry_run and not args.live:
        print("Specify --dry-run or --live")
        return

    dry_run = not args.live

    print("=" * 70, flush=True)
    print("BRAND GALLERY SCRAPER (gallery-2 / MultiImage)", flush=True)
    print("=" * 70, flush=True)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}", flush=True)
    print(f"Max images per brand: {MAX_GALLERY_IMAGES}", flush=True)
    if args.only_missing:
        print("Filter: only brands missing gallery", flush=True)
    if args.limit:
        print(f"Limit: {args.limit} brands", flush=True)

    shopify_map = load_brands_json()
    print(f"Loaded {len(shopify_map)} brands from brands.json", flush=True)

    client = WebflowClient()
    print("\nFetching brands from Webflow...", flush=True)
    brands = client.get_items(BRANDS_COLLECTION_ID)
    print(f"Loaded {len(brands)} brands", flush=True)

    if args.only_missing:
        brands = [b for b in brands if not b.get('fieldData', {}).get('gallery-2')]
        print(f"Brands missing gallery: {len(brands)}", flush=True)

    if args.limit > 0:
        brands = brands[:args.limit]

    print(f"\nProcessing {len(brands)} brands...", flush=True)
    print("=" * 70, flush=True)

    updated_ids = []
    found_count = 0
    skipped_no_url = 0
    skipped_no_images = 0
    image_counts = []  # track how many images per brand for stats

    for i, brand in enumerate(brands, 1):
        item_id = brand['id']
        fd = brand.get('fieldData', {})
        name = fd.get('name', 'Unknown')
        slug = fd.get('slug', '')

        has_gallery = bool(fd.get('gallery-2'))

        print(f"\n[{i}/{len(brands)}] {name} (slug: {slug})", flush=True)
        if has_gallery:
            existing = fd.get('gallery-2', [])
            print(f"  Already has gallery ({len(existing)} images)", flush=True)

        cms_external_link = fd.get('external-link', '') or ''
        brand_url = resolve_brand_url(slug, cms_external_link, shopify_map)

        if not brand_url:
            print(f"  SKIP — no website URL", flush=True)
            skipped_no_url += 1
            continue

        print(f"  Website: {brand_url}", flush=True)

        # Scrape
        gallery_images = scrape_gallery_images(brand_url, verbose=args.verbose)

        # Validate images (sample validation — check first, middle, last)
        if gallery_images:
            validated = []
            for idx, img_url in enumerate(gallery_images):
                # Validate every image to ensure quality
                if is_valid_image_url(img_url):
                    validated.append(img_url)
                elif args.verbose:
                    print(f"    Validation failed: {img_url[:60]}", flush=True)
            gallery_images = validated

        if not gallery_images:
            print(f"  Gallery: no images found", flush=True)
            skipped_no_images += 1
            continue

        print(f"  Gallery: {len(gallery_images)} images", flush=True)
        found_count += 1
        image_counts.append(len(gallery_images))

        if args.verbose:
            for j, url in enumerate(gallery_images):
                print(f"    [{j+1}] {url[:75]}", flush=True)

        # Build MultiImage array for gallery-2
        gallery_data = [{'url': url} for url in gallery_images]
        field_data = {'gallery-2': gallery_data}

        if not dry_run:
            if client.update_item(BRANDS_COLLECTION_ID, item_id, field_data):
                print(f"  UPDATED", flush=True)
                updated_ids.append(item_id)
            else:
                print(f"  UPDATE FAILED", flush=True)
            time.sleep(0.5)
        else:
            updated_ids.append(item_id)

        time.sleep(2)

    # Publish
    if not dry_run and updated_ids:
        print(f"\n{'='*70}", flush=True)
        print(f"Publishing {len(updated_ids)} updated brands...", flush=True)
        client.publish_items(BRANDS_COLLECTION_ID, updated_ids)

    # Summary
    print(f"\n{'='*70}", flush=True)
    print("SUMMARY", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"Brands processed:       {len(brands)}", flush=True)
    print(f"Galleries populated:    {found_count}", flush=True)
    print(f"Skipped (no URL):       {skipped_no_url}", flush=True)
    print(f"Skipped (no images):    {skipped_no_images}", flush=True)
    if image_counts:
        avg = sum(image_counts) / len(image_counts)
        print(f"Avg images per brand:   {avg:.1f}", flush=True)
        print(f"Min/Max images:         {min(image_counts)} / {max(image_counts)}", flush=True)
    print(f"{'Updated' if not dry_run else 'Would update'}: {len(updated_ids)}", flush=True)
    print("\nDone!", flush=True)


if __name__ == "__main__":
    main()
