#!/usr/bin/env python3
"""
Scrape brand product-range images and founder photos for the Brands collection.

Product range images (image-2 through image-5):
  Tier 1: Shopify /collections.json — collection images (best quality)
  Tier 2: Shopify /products.json — one product per product_type for variety
  Tier 3: Homepage HTML scraping — featured/collection section images

Founder images (founder-image):
  Searches about/team pages for images matching the CMS founder name.

Usage:
    PYTHONUNBUFFERED=1 python3 scrape_brand_range_images.py --dry-run
    PYTHONUNBUFFERED=1 python3 scrape_brand_range_images.py --live
    PYTHONUNBUFFERED=1 python3 scrape_brand_range_images.py --dry-run --limit 5 --verbose
    PYTHONUNBUFFERED=1 python3 scrape_brand_range_images.py --live --skip-founders
    PYTHONUNBUFFERED=1 python3 scrape_brand_range_images.py --live --only-founders
    PYTHONUNBUFFERED=1 python3 scrape_brand_range_images.py --live --only-missing
"""

import os
import sys
import time
import json
import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

import requests
from bs4 import BeautifulSoup

WEBFLOW_API_BASE = "https://api.webflow.com/v2"
BRANDS_COLLECTION_ID = "697d981be773ae7dbfc093ed"

RANGE_FIELDS = ['image-2', 'image-3', 'image-4', 'image-5']

# Shopify collection handles to skip — not product ranges
SKIP_COLLECTION_HANDLES = {
    'all', 'frontpage', 'homepage', 'sale', 'clearance', 'outlet',
    'gift-cards', 'gift-card', 'gifts', 'gift-sets', 'bundles', 'bundle',
    'best-sellers', 'bestsellers', 'new', 'new-arrivals', 'new-in',
    'featured', 'shop-all', 'shop', 'everything', 'products',
    'samples', 'sample', 'mini', 'minis', 'travel', 'travel-size',
    'subscription', 'subscriptions', 'rewards', 'loyalty',
    'press', 'wholesale', 'b2b', 'retail',
}

# Words in collection title that suggest non-product collections
SKIP_COLLECTION_TITLE_WORDS = {
    'sale', 'clearance', 'gift card', 'gift set', 'bundle',
    'sample', 'mini', 'travel size', 'subscription',
    'wholesale', 'press', 'retailer', 'best seller',
    'new arrival', 'shop all', 'all products',
}

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

# Press/media logo keywords (reused from scrape_brand_logos.py)
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

# Known brand websites fallback (from scrape_brand_logos.py)
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
# Utility functions (reused patterns from scrape_brand_logos.py)
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
    """Fetch URL with exponential backoff retry."""
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
    """Check if URL looks like a non-product image (icon, badge, payment, etc.)."""
    path = urlparse(url).path.lower()
    filename = path.rsplit('/', 1)[-1] if '/' in path else path
    filename = filename.replace('%20', '-').replace('+', '-').replace('_', '-')
    for pattern in SKIP_IMAGE_PATTERNS:
        if pattern in filename:
            return True
    return is_press_logo(url)


def is_valid_image_url(url: str) -> bool:
    """Validate via HEAD request that URL returns image content."""
    if not url or not url.startswith('http'):
        return False
    try:
        resp = requests.head(url, headers=get_random_headers(), timeout=10, allow_redirects=True)
        ct = resp.headers.get('Content-Type', '')
        return resp.ok and 'image/' in ct
    except requests.RequestException:
        return False


def normalize_shopify_cdn_url(url: str, width: int = 600) -> str:
    """Normalize Shopify CDN image URL to a consistent size."""
    if 'cdn.shopify.com' not in url:
        return url
    # Remove existing size suffix like _200x200 or _small
    url = re.sub(r'_(\d+x\d*|\d*x\d+|small|medium|large|grande|master|compact|pico|icon)\.', '.', url)
    # Insert width before extension
    url = re.sub(r'\.([a-zA-Z]{3,4})(\?|$)', rf'_{width}x.\1\2', url)
    # Remove cache-busting query params
    url = re.sub(r'\?v=\d+', '', url)
    return url


def load_brands_json() -> Dict[str, str]:
    """Load brands.json and return slug -> shopify_domain mapping."""
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
    """Resolve brand website URL via fallback chain."""
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


def make_absolute(src: str, base_url: str) -> str:
    """Convert a potentially relative URL to absolute."""
    if not src or src.startswith('data:'):
        return ''
    if not src.startswith('http'):
        return urljoin(base_url, src)
    return src


# ---------------------------------------------------------------------------
# Tier 1: Shopify /collections.json
# ---------------------------------------------------------------------------

def is_product_collection(handle: str, title: str) -> bool:
    """Check if a Shopify collection is a real product range (not sale/gift/etc.)."""
    if handle in SKIP_COLLECTION_HANDLES:
        return False
    title_lower = title.lower()
    for word in SKIP_COLLECTION_TITLE_WORDS:
        if word in title_lower:
            return False
    return True


def scrape_shopify_collections(brand_url: str, verbose: bool = False) -> List[str]:
    """
    Tier 1: Fetch collection images from Shopify /collections.json.
    Returns up to 4 collection image URLs.
    """
    parsed = urlparse(brand_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    test_url = f"{base}/collections.json?limit=1"

    resp = fetch_with_retry(test_url, accept_json=True)
    if not resp or resp.status_code != 200:
        if verbose:
            print(f"    [Tier1] Not Shopify or /collections.json blocked", flush=True)
        return []

    try:
        data = resp.json()
        if 'collections' not in data:
            return []
    except (json.JSONDecodeError, ValueError):
        return []

    if verbose:
        print(f"    [Tier1] Shopify detected, fetching collections...", flush=True)

    # Fetch all collections (paginated)
    all_collections = []
    page = 1
    while True:
        url = f"{base}/collections.json?limit=250&page={page}"
        resp = fetch_with_retry(url, accept_json=True)
        if not resp or not resp.ok:
            break
        try:
            data = resp.json()
            batch = data.get('collections', [])
            all_collections.extend(batch)
            if len(batch) < 250:
                break
            page += 1
            time.sleep(0.5)
        except (json.JSONDecodeError, ValueError):
            break

    if verbose:
        print(f"    [Tier1] Found {len(all_collections)} total collections", flush=True)

    # Filter to product collections with images
    images = []
    for col in all_collections:
        handle = col.get('handle', '')
        title = col.get('title', '')
        image = col.get('image')

        if not image or not image.get('src'):
            continue
        if not is_product_collection(handle, title):
            if verbose:
                print(f"    [Tier1] Skip non-product: {handle}", flush=True)
            continue

        img_url = image['src']
        img_url = normalize_shopify_cdn_url(img_url)

        if is_svg(img_url) or is_skip_image(img_url):
            continue

        if verbose:
            print(f"    [Tier1] Collection '{title}': {img_url[:70]}", flush=True)
        images.append(img_url)

        if len(images) >= 4:
            break

    return images


# ---------------------------------------------------------------------------
# Tier 2: Shopify /products.json (variety by product_type)
# ---------------------------------------------------------------------------

def scrape_shopify_products(brand_url: str, needed: int = 4, verbose: bool = False) -> List[str]:
    """
    Tier 2: Fetch product images from Shopify /products.json.
    Picks one product per product_type for variety.
    Returns up to `needed` image URLs.
    """
    parsed = urlparse(brand_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    url = f"{base}/products.json?limit=50"

    resp = fetch_with_retry(url, accept_json=True)
    if not resp or resp.status_code != 200:
        if verbose:
            print(f"    [Tier2] /products.json not available", flush=True)
        return []

    try:
        data = resp.json()
        products = data.get('products', [])
    except (json.JSONDecodeError, ValueError):
        return []

    if not products:
        return []

    if verbose:
        print(f"    [Tier2] Got {len(products)} products", flush=True)

    # Pick one product per product_type for visual variety
    seen_types = set()
    images = []

    for product in products:
        product_type = (product.get('product_type') or 'unknown').strip().lower()

        # Skip if we already have one from this type
        if product_type in seen_types:
            continue

        # Get the first image
        product_images = product.get('images', [])
        if not product_images:
            continue

        img_url = product_images[0].get('src', '')
        if not img_url:
            continue

        img_url = normalize_shopify_cdn_url(img_url)

        if is_svg(img_url) or is_skip_image(img_url):
            continue

        seen_types.add(product_type)
        images.append(img_url)

        if verbose:
            title = product.get('title', '?')[:40]
            print(f"    [Tier2] {product_type}: {title} → {img_url[:60]}", flush=True)

        if len(images) >= needed:
            break

    return images


# ---------------------------------------------------------------------------
# Tier 3: Homepage HTML scraping (non-Shopify)
# ---------------------------------------------------------------------------

def scrape_homepage_images(brand_url: str, verbose: bool = False) -> List[str]:
    """
    Tier 3: Scrape product/collection images from homepage HTML.
    Looks for images in featured/collection sections.
    Returns up to 4 image URLs.
    """
    resp = fetch_with_retry(brand_url)
    if not resp or not resp.ok:
        if verbose:
            print(f"    [Tier3] Could not fetch homepage", flush=True)
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    base_url = resp.url

    # Collect candidate images from likely product/collection sections
    candidates = []
    seen_urls = set()

    # Strategy A: Look for images in collection/category/featured sections
    section_selectors = [
        '[class*="collection"] img',
        '[class*="category"] img',
        '[class*="featured"] img',
        '[class*="product"] img',
        '[class*="range"] img',
        '[class*="shop"] img',
        '[class*="hero"] img',
        '[class*="banner"] img',
        '[id*="collection"] img',
        '[id*="category"] img',
        '[id*="featured"] img',
    ]

    for selector in section_selectors:
        for img in soup.select(selector):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or ''
            src = make_absolute(src, base_url)
            if not src or src in seen_urls:
                continue
            if is_svg(src) or is_skip_image(src):
                continue

            # Check natural dimensions from attributes (skip tiny images)
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

    # Strategy B: Look for larger images anywhere on the page
    if len(candidates) < 4:
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or ''
            src = make_absolute(src, base_url)
            if not src or src in seen_urls:
                continue
            if is_svg(src) or is_skip_image(src):
                continue

            # Require size hints suggesting a real product image
            width = img.get('width', '')
            height = img.get('height', '')
            try:
                w = int(width) if width else 0
                h = int(height) if height else 0
                if (w > 0 and w < 150) or (h > 0 and h < 150):
                    continue
            except (ValueError, TypeError):
                pass

            # Check srcset for size hints
            srcset = img.get('srcset', '')
            if srcset:
                # If srcset mentions sizes > 300px, it's likely a real image
                sizes = re.findall(r'(\d+)w', srcset)
                if sizes and max(int(s) for s in sizes) < 200:
                    continue

            seen_urls.add(src)
            candidates.append(src)

    # Normalize Shopify CDN URLs if present
    candidates = [normalize_shopify_cdn_url(url) for url in candidates]

    if verbose:
        print(f"    [Tier3] Found {len(candidates)} candidate images from HTML", flush=True)
        for c in candidates[:6]:
            print(f"    [Tier3]   {c[:80]}", flush=True)

    return candidates[:4]


# ---------------------------------------------------------------------------
# Founder image scraping
# ---------------------------------------------------------------------------

ABOUT_PATHS = [
    '/pages/about', '/pages/about-us', '/pages/our-story',
    '/pages/our-founder', '/pages/founders', '/pages/the-founder',
    '/pages/meet-the-founder', '/pages/the-brand',
    '/about', '/about-us', '/our-story',
]


def find_about_page_url(brand_url: str, soup: Optional[BeautifulSoup] = None,
                        verbose: bool = False) -> Optional[str]:
    """Find the about/story page URL for a brand."""
    parsed = urlparse(brand_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    # Try common paths first
    for path in ABOUT_PATHS:
        url = f"{base}{path}"
        try:
            resp = requests.head(url, headers=get_random_headers(), timeout=10, allow_redirects=True)
            if resp.ok:
                if verbose:
                    print(f"    [Founder] Found about page: {path}", flush=True)
                return resp.url  # Use final URL after redirects
        except requests.RequestException:
            continue
        time.sleep(0.3)

    # Fallback: scan homepage links for about/story
    if soup is None:
        resp = fetch_with_retry(brand_url)
        if resp and resp.ok:
            soup = BeautifulSoup(resp.text, 'html.parser')

    if soup:
        about_keywords = ['about', 'story', 'founder', 'our-story', 'the-brand', 'meet']
        homepage_path = parsed.path.rstrip('/') or ''
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            text = a.get_text(strip=True).lower()
            combined = href + ' ' + text
            if any(kw in combined for kw in about_keywords):
                url = make_absolute(a['href'], brand_url)
                if not url:
                    continue
                link_parsed = urlparse(url)
                # Must be same domain
                if link_parsed.netloc != parsed.netloc:
                    continue
                # Must not be the homepage itself
                link_path = link_parsed.path.rstrip('/') or ''
                if link_path == homepage_path:
                    continue
                if verbose:
                    print(f"    [Founder] Found about link: {url[:70]}", flush=True)
                return url

    return None


def parse_founder_names(raw: str) -> List[str]:
    """
    Parse the CMS founder field into individual names.
    Handles formats like:
      "Jill Munson, Britta Plug, Gianna De La Torre (2018)"
      "Emily Weiss (2014)"
      "Guive Assadi & Joan Audi"
    Strips year in parentheses and splits on comma / ampersand.
    """
    # Remove year in parentheses: "(2018)", "(2014)"
    cleaned = re.sub(r'\s*\(\d{4}\)\s*', '', raw).strip()
    if not cleaned:
        return []
    # Split on comma or ampersand
    parts = re.split(r'\s*[,&]\s*', cleaned)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 2]


def scrape_founder_image(brand_url: str, founder_name: str,
                         verbose: bool = False) -> Optional[str]:
    """
    Scrape founder photo from about/team page.
    Matches images where alt text contains the founder name,
    or images in founder/team/bio sections.
    """
    if not founder_name or not founder_name.strip():
        return None

    # Parse individual names from the raw field
    names = parse_founder_names(founder_name)
    if not names:
        return None

    # Build search tokens: full names + last names
    search_names = []
    search_last_names = []
    for n in names:
        search_names.append(n.lower())
        parts = n.split()
        if len(parts) > 1:
            search_last_names.append(parts[-1].lower())

    if verbose:
        print(f"    [Founder] Searching for: {', '.join(names)}", flush=True)

    about_url = find_about_page_url(brand_url, verbose=verbose)
    if not about_url:
        if verbose:
            print(f"    [Founder] No about page found", flush=True)
        return None

    resp = fetch_with_retry(about_url)
    if not resp or not resp.ok:
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    base_url = resp.url

    # Strategy 1: <img> where alt contains any founder name
    for img in soup.find_all('img'):
        alt = (img.get('alt') or '').lower()
        if not alt:
            continue

        # Check if alt contains any full name or last name
        name_match = any(n in alt for n in search_names) or \
                     any(ln in alt for ln in search_last_names)
        if not name_match:
            continue

        src = img.get('src') or img.get('data-src') or ''
        src = make_absolute(src, base_url)
        if not src or is_svg(src) or is_skip_image(src):
            continue

        if verbose:
            print(f"    [Founder] Alt match: '{alt}' → {src[:70]}", flush=True)
        return src

    # Strategy 2: Images in founder/team/bio sections (narrower selectors)
    # Only use specific founder/team/bio selectors — skip generic "about"/"story"
    # to avoid matching unrelated product/lifestyle images on about pages
    founder_selectors = [
        '[class*="founder"] img',
        '[class*="team"] img',
        '[class*="bio"] img',
        '[id*="founder"] img',
        '[id*="team"] img',
    ]

    for selector in founder_selectors:
        for img in soup.select(selector):
            src = img.get('src') or img.get('data-src') or ''
            src = make_absolute(src, base_url)
            if not src or is_svg(src) or is_skip_image(src):
                continue

            # Avoid very small images (icons, badges)
            width = img.get('width', '')
            height = img.get('height', '')
            try:
                if width and int(width) < 80:
                    continue
                if height and int(height) < 80:
                    continue
            except (ValueError, TypeError):
                pass

            if verbose:
                print(f"    [Founder] Section match ({selector}): {src[:70]}", flush=True)
            return src

    if verbose:
        print(f"    [Founder] No founder image found on about page", flush=True)
    return None


# ---------------------------------------------------------------------------
# Webflow client (same pattern as scrape_brand_logos.py)
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

def scrape_range_images(brand_url: str, verbose: bool = False) -> List[str]:
    """
    Three-tier approach to get up to 4 product range images.
    Returns list of validated image URLs.
    """
    # Tier 1: Shopify /collections.json
    images = scrape_shopify_collections(brand_url, verbose=verbose)

    # Tier 2: Shopify /products.json if < 2 collection images
    if len(images) < 2:
        needed = 4 - len(images)
        product_images = scrape_shopify_products(brand_url, needed=needed, verbose=verbose)
        # Dedupe
        existing = set(images)
        for img in product_images:
            if img not in existing:
                images.append(img)
                existing.add(img)
            if len(images) >= 4:
                break
        time.sleep(0.5)

    # Tier 3: Homepage HTML if still < 2 images
    if len(images) < 2:
        html_images = scrape_homepage_images(brand_url, verbose=verbose)
        existing = set(images)
        for img in html_images:
            if img not in existing:
                images.append(img)
                existing.add(img)
            if len(images) >= 4:
                break

    return images[:4]


def process_brand(brand_url: str, founder_name: str,
                  skip_founders: bool, only_founders: bool,
                  verbose: bool = False) -> Tuple[List[str], Optional[str]]:
    """
    Process a single brand. Returns (range_images, founder_image_url).
    """
    range_images = []
    founder_url = None

    if not only_founders:
        range_images = scrape_range_images(brand_url, verbose=verbose)

    if not skip_founders and founder_name:
        founder_url = scrape_founder_image(brand_url, founder_name, verbose=verbose)
        if founder_url and not is_valid_image_url(founder_url):
            if verbose:
                print(f"    [Founder] Image validation failed, discarding", flush=True)
            founder_url = None

    return range_images, founder_url


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape brand range images and founder photos")
    parser.add_argument("--dry-run", action="store_true", help="Preview without updating Webflow")
    parser.add_argument("--live", action="store_true", help="Actually update Webflow")
    parser.add_argument("--only-missing", action="store_true", help="Only brands missing range images")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of brands")
    parser.add_argument("--verbose", action="store_true", help="Show detailed scraping info")
    parser.add_argument("--skip-founders", action="store_true", help="Skip founder image scraping")
    parser.add_argument("--only-founders", action="store_true", help="Only scrape founder images")
    args = parser.parse_args()

    if not args.dry_run and not args.live:
        print("Specify --dry-run or --live")
        return

    if args.skip_founders and args.only_founders:
        print("Cannot use --skip-founders and --only-founders together")
        return

    dry_run = not args.live

    print("=" * 70, flush=True)
    print("BRAND RANGE & FOUNDER IMAGE SCRAPER", flush=True)
    print("=" * 70, flush=True)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}", flush=True)
    if args.skip_founders:
        print("Skipping founder images", flush=True)
    if args.only_founders:
        print("Only scraping founder images", flush=True)
    if args.only_missing:
        print("Filter: only brands missing images", flush=True)
    if args.limit:
        print(f"Limit: {args.limit} brands", flush=True)

    # Load brands.json shopify domain mapping
    shopify_map = load_brands_json()
    print(f"Loaded {len(shopify_map)} brands from brands.json", flush=True)

    # Fetch brands from Webflow
    client = WebflowClient()
    print("\nFetching brands from Webflow...", flush=True)
    brands = client.get_items(BRANDS_COLLECTION_ID)
    print(f"Loaded {len(brands)} brands", flush=True)

    # Filter if --only-missing
    if args.only_missing:
        def is_missing(b):
            fd = b.get('fieldData', {})
            if args.only_founders:
                return not (fd.get('founder-image') or {}).get('url')
            # Missing if image-2 is empty
            return not (fd.get('image-2') or {}).get('url')
        brands = [b for b in brands if is_missing(b)]
        print(f"Brands missing images: {len(brands)}", flush=True)

    if args.limit > 0:
        brands = brands[:args.limit]

    print(f"\nProcessing {len(brands)} brands...", flush=True)
    print("=" * 70, flush=True)

    # Stats
    updated_ids = []
    range_found = 0
    founder_found = 0
    skipped_no_url = 0
    skipped_no_images = 0
    tier_counts = {'tier1': 0, 'tier2': 0, 'tier3': 0}

    for i, brand in enumerate(brands, 1):
        item_id = brand['id']
        fd = brand.get('fieldData', {})
        name = fd.get('name', 'Unknown')
        slug = fd.get('slug', '')
        founder_name = fd.get('founder', '') or ''

        # Current image state
        has_range = bool((fd.get('image-2') or {}).get('url'))
        has_founder = bool((fd.get('founder-image') or {}).get('url'))

        print(f"\n[{i}/{len(brands)}] {name} (slug: {slug})", flush=True)
        if has_range:
            print(f"  Already has range images", flush=True)
        if has_founder:
            print(f"  Already has founder image", flush=True)
        if founder_name:
            print(f"  Founder: {founder_name}", flush=True)

        # Resolve brand URL
        cms_external_link = fd.get('external-link', '') or ''
        brand_url = resolve_brand_url(slug, cms_external_link, shopify_map)

        if not brand_url:
            print(f"  SKIP — no website URL", flush=True)
            skipped_no_url += 1
            continue

        print(f"  Website: {brand_url}", flush=True)

        # Scrape
        range_images, founder_url = process_brand(
            brand_url, founder_name,
            skip_founders=args.skip_founders,
            only_founders=args.only_founders,
            verbose=args.verbose,
        )

        # Validate range images
        validated_range = []
        for img_url in range_images:
            if is_valid_image_url(img_url):
                validated_range.append(img_url)
            elif args.verbose:
                print(f"    Range image validation failed: {img_url[:60]}", flush=True)

        # Report what we found
        if validated_range:
            print(f"  Range images: {len(validated_range)} found", flush=True)
            range_found += 1
            for j, url in enumerate(validated_range):
                print(f"    {RANGE_FIELDS[j]}: {url[:70]}", flush=True)
        elif not args.only_founders:
            print(f"  Range images: none found", flush=True)

        if founder_url:
            print(f"  Founder image: {founder_url[:70]}", flush=True)
            founder_found += 1
        elif not args.skip_founders and founder_name:
            print(f"  Founder image: not found", flush=True)

        # Build field_data for update
        field_data = {}
        for j, url in enumerate(validated_range[:4]):
            field_data[RANGE_FIELDS[j]] = {'url': url}
        if founder_url:
            field_data['founder-image'] = {'url': founder_url}

        if not field_data:
            skipped_no_images += 1
            continue

        # Update Webflow
        if not dry_run:
            if client.update_item(BRANDS_COLLECTION_ID, item_id, field_data):
                print(f"  UPDATED ({len(field_data)} fields)", flush=True)
                updated_ids.append(item_id)
            else:
                print(f"  UPDATE FAILED", flush=True)
            time.sleep(0.5)
        else:
            updated_ids.append(item_id)

        # Delay between brands
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
    print(f"Brands processed:     {len(brands)}", flush=True)
    print(f"Range images found:   {range_found}", flush=True)
    print(f"Founder images found: {founder_found}", flush=True)
    print(f"Skipped (no URL):     {skipped_no_url}", flush=True)
    print(f"Skipped (no images):  {skipped_no_images}", flush=True)
    print(f"{'Updated' if not dry_run else 'Would update'}: {len(updated_ids)}", flush=True)
    print("\nDone!", flush=True)


if __name__ == "__main__":
    main()
