#!/usr/bin/env python3
"""
Scrape brand logos from brand websites and update Webflow Brands collection.

Resolves brand website URL via fallback chain:
  1. CMS `website` field (if non-Credo)
  2. brands.json shopify_domain
  3. BRAND_WEBSITES hardcoded dict

Scrapes logos via ordered heuristics:
  1. Schema.org Organization.logo in LD+JSON
  2. <img> inside <header>/<nav> with "logo" in class/id/alt/src
  3. CSS selectors: [class*="logo"] img, [id*="logo"] img
  4. Apple touch icon
  5. og:image meta tag (last resort)

Falls back to Clearbit Logo API if scraping fails or finds SVG only.

Usage:
    PYTHONUNBUFFERED=1 python3 scrape_brand_logos.py --dry-run
    PYTHONUNBUFFERED=1 python3 scrape_brand_logos.py --live
    PYTHONUNBUFFERED=1 python3 scrape_brand_logos.py --live --only-missing
    PYTHONUNBUFFERED=1 python3 scrape_brand_logos.py --live --limit 5 --verbose
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

# Known brand websites (from enrich_brands.py)
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

# Press/media logo patterns — these appear as "as seen in" badges in headers
# and must be skipped so we don't mistake them for the brand's own logo.
# Checked against FILENAME only (not domain) to avoid blocking brand domains.
PRESS_LOGO_KEYWORDS = [
    'bazaar', 'harpers-bazaar', 'allure', 'vogue', 'glamour',
    'cosmopolitan', 'cosmo', 'instyle', 'refinery29', 'byrdie',
    'teen-vogue', 'nylon', 'bustle', 'popsugar', 'gq', 'esquire',
    'vanity-fair', 'marie-claire', 'self-magazine', 'today-show',
    'good-morning', 'oprah', 'forbes', 'nytimes', 'new-york-times',
    'wall-street', 'wsj', 'cnn', 'bbc', 'people-magazine',
    'womens-health', 'mens-health', 'well-good', 'well-and-good',
    'goop-logo', 'sephora-logo', 'nordstrom-logo', 'ulta-logo',
    'guccis-guide', 'guccis_guide', 'guccisguide', 'who-what-wear', 'coveteur',
    'editorialist', 'the-cut', 'vulture', 'fashionista', 'glossy',
    'beauty-independent', 'wwd', 'womens-wear', 'publisher',
]

# User agents to rotate (from scrape_brand_images.py)
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
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
            delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
            if attempt > 0:
                print(f"    Retry {attempt + 1}/{max_retries} after {delay:.1f}s...", flush=True)
                time.sleep(delay)

            resp = requests.get(url, headers=get_random_headers(), timeout=20, allow_redirects=True)

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
    """Check if URL points to an SVG."""
    return '.svg' in urlparse(url).path.lower() or url.strip().startswith('data:image/svg')


def is_press_logo(url: str) -> bool:
    """Check if URL filename looks like a press/media 'as seen in' badge."""
    # Only check the filename, not the domain (avoids blocking e.g. tataharperskincare.com)
    path = urlparse(url).path
    filename = path.rsplit('/', 1)[-1] if '/' in path else path
    filename = filename.lower().replace('%20', '-').replace('+', '-').replace('_', '-')
    for keyword in PRESS_LOGO_KEYWORDS:
        if keyword in filename:
            return True
    return False


def is_valid_image_url(url: str) -> bool:
    """Validate that URL returns an image Content-Type via HEAD request."""
    if not url or not url.startswith('http'):
        return False
    try:
        resp = requests.head(url, headers=get_random_headers(), timeout=10, allow_redirects=True)
        ct = resp.headers.get('Content-Type', '')
        return resp.ok and ('image/' in ct)
    except requests.RequestException:
        return False


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
                # Normalize: ensure https://
                if not domain.startswith('http'):
                    domain = f'https://{domain}'
                mapping[slug] = domain
        return mapping
    except (json.JSONDecodeError, KeyError):
        return {}


def resolve_brand_url(slug: str, cms_external_link: str, shopify_map: Dict[str, str]) -> Optional[str]:
    """Resolve brand website URL via fallback chain."""
    # 1. CMS external-link field (now "Brand Home") — skip if it points to Credo
    if cms_external_link:
        parsed = urlparse(cms_external_link)
        domain = parsed.netloc.lower().replace('www.', '')
        if 'credo' not in domain and 'credobeauty' not in domain:
            return cms_external_link

    # 2. brands.json shopify_domain
    if slug in shopify_map:
        return shopify_map[slug]

    # 3. BRAND_WEBSITES hardcoded dict
    if slug in BRAND_WEBSITES:
        return BRAND_WEBSITES[slug]

    return None


def scrape_logo_from_html(url: str, verbose: bool = False) -> Optional[str]:
    """Scrape logo URL from a brand website using ordered heuristics."""
    resp = fetch_with_retry(url)
    if not resp or not resp.ok:
        if verbose:
            print(f"    Could not fetch {url}", flush=True)
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    base_url = resp.url  # Use final URL after redirects

    def make_absolute(src: str) -> str:
        if not src:
            return ''
        if src.startswith('data:'):
            return ''
        if not src.startswith('http'):
            return urljoin(base_url, src)
        return src

    # --- Heuristic 1: Schema.org Organization.logo in LD+JSON ---
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '{}')
            # Handle @graph arrays
            items = [data] if isinstance(data, dict) else data if isinstance(data, list) else []
            if isinstance(data, dict) and '@graph' in data:
                items = data['@graph']
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get('@type') in ('Organization', 'Brand', 'Corporation', 'WebSite'):
                    logo = item.get('logo')
                    if isinstance(logo, dict):
                        logo = logo.get('url', '')
                    if isinstance(logo, str) and logo:
                        logo = make_absolute(logo)
                        if logo and not is_svg(logo) and not is_press_logo(logo):
                            if verbose:
                                print(f"    [LD+JSON] {logo}", flush=True)
                            return logo
                        elif logo and is_press_logo(logo) and verbose:
                            print(f"    [LD+JSON] SKIP press logo: {logo[:60]}", flush=True)
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    # --- Heuristic 2: <img> inside <header>/<nav> with "logo" in class/id/alt/src ---
    for container_tag in ('header', 'nav'):
        for container in soup.find_all(container_tag):
            for img in container.find_all('img'):
                attrs_text = ' '.join([
                    ' '.join(img.get('class', [])),
                    img.get('id', ''),
                    img.get('alt', ''),
                    img.get('src', ''),
                ]).lower()
                if 'logo' in attrs_text:
                    src = img.get('src') or img.get('data-src') or ''
                    src = make_absolute(src)
                    if src and not is_svg(src) and not is_press_logo(src):
                        if verbose:
                            print(f"    [header/nav img] {src}", flush=True)
                        return src
                    elif src and is_press_logo(src) and verbose:
                        print(f"    [header/nav] SKIP press logo: {src[:60]}", flush=True)

    # --- Heuristic 3: CSS selectors for logo images ---
    logo_selectors = [
        '[class*="logo"] img',
        '[id*="logo"] img',
        'a[class*="logo"] img',
        '.header-logo img',
        '#logo img',
    ]
    for selector in logo_selectors:
        for img in soup.select(selector):
            src = img.get('src') or img.get('data-src') or ''
            src = make_absolute(src)
            if src and not is_svg(src) and not is_press_logo(src):
                if verbose:
                    print(f"    [CSS selector: {selector}] {src}", flush=True)
                return src
            elif src and is_press_logo(src) and verbose:
                print(f"    [CSS] SKIP press logo: {src[:60]}", flush=True)

    # --- Heuristic 4: Apple touch icon ---
    for link in soup.find_all('link', rel=lambda r: r and 'apple-touch-icon' in ' '.join(r if isinstance(r, list) else [r])):
        href = link.get('href', '')
        href = make_absolute(href)
        if href and not is_svg(href):
            if verbose:
                print(f"    [apple-touch-icon] {href}", flush=True)
            return href

    # og:image is NOT returned here — it's a weak signal (often a promo banner).
    # The caller should try Clearbit first, then fall back to og:image.
    return None


def scrape_og_image(url: str, verbose: bool = False) -> Optional[str]:
    """Extract og:image from a URL. Separate from main scraper since it's a weak signal."""
    resp = fetch_with_retry(url)
    if not resp or not resp.ok:
        return None
    soup = BeautifulSoup(resp.text, 'html.parser')
    base_url = resp.url
    og = soup.find('meta', property='og:image')
    if og:
        content = og.get('content', '')
        if content and not content.startswith('data:'):
            if not content.startswith('http'):
                content = urljoin(base_url, content)
            if not is_svg(content):
                if verbose:
                    print(f"    [og:image fallback] {content[:80]}", flush=True)
                return content
    return None


def clearbit_logo(domain: str, verbose: bool = False) -> Optional[str]:
    """Get logo from Clearbit Logo API as fallback."""
    # Strip protocol and www
    parsed = urlparse(domain if '://' in domain else f'https://{domain}')
    clean_domain = parsed.netloc or parsed.path
    clean_domain = clean_domain.replace('www.', '')

    url = f'https://logo.clearbit.com/{clean_domain}'
    if verbose:
        print(f"    [Clearbit] Trying {url}", flush=True)

    try:
        resp = requests.head(url, timeout=10, allow_redirects=True)
        ct = resp.headers.get('Content-Type', '')
        if resp.ok and 'image/' in ct:
            if verbose:
                print(f"    [Clearbit] Found logo", flush=True)
            return url
    except requests.RequestException:
        pass

    return None


def guess_domains_from_slug(slug: str, name: str) -> List[str]:
    """Generate candidate domains from brand slug/name for Clearbit lookup."""
    candidates = []
    # slug as-is: "tower-28" → "tower-28.com"
    candidates.append(f'{slug}.com')
    # slug without hyphens: "tower28.com"
    no_hyphens = slug.replace('-', '')
    if no_hyphens != slug:
        candidates.append(f'{no_hyphens}.com')
    # slug + "beauty": "tower-28beauty.com", "tower28beauty.com"
    candidates.append(f'{slug}beauty.com')
    candidates.append(f'{no_hyphens}beauty.com')
    # slug + "cosmetics"
    candidates.append(f'{slug}cosmetics.com')
    # Name-based: lowercase, no spaces
    name_clean = re.sub(r'[^a-z0-9]', '', name.lower())
    if name_clean and name_clean != no_hyphens:
        candidates.append(f'{name_clean}.com')
    # Dedupe while preserving order
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def clearbit_logo_from_guesses(slug: str, name: str, verbose: bool = False) -> Optional[str]:
    """Try Clearbit with guessed domains when no website URL is known."""
    guesses = guess_domains_from_slug(slug, name)
    if verbose:
        print(f"    [Clearbit guess] Trying domains: {', '.join(guesses[:4])}", flush=True)
    for domain in guesses:
        result = clearbit_logo(domain, verbose=verbose)
        if result:
            return result
    return None


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
        """Fetch all items from a collection (paginated)."""
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
        """Update an item's fields."""
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
        """Publish items in batches of 100."""
        if not self.site_id:
            print("  WEBFLOW_SITE_ID not set, skipping publish", flush=True)
            return False

        for i in range(0, len(item_ids), 100):
            batch = item_ids[i:i + 100]
            url = f'{WEBFLOW_API_BASE}/collections/{collection_id}/items/publish'
            resp = self.session.post(url, json={'itemIds': batch}, headers={'Content-Type': 'application/json'})

            if resp.status_code == 429:
                time.sleep(int(resp.headers.get('Retry-After', 60)))
                resp = self.session.post(url, json={'itemIds': batch}, headers={'Content-Type': 'application/json'})

            if not resp.ok:
                print(f"    Publish error (batch {i // 100 + 1}): {resp.status_code} {resp.text[:200]}", flush=True)
                return False

            print(f"  Published batch {i // 100 + 1} ({len(batch)} items)", flush=True)
            time.sleep(1.0)

        return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape brand logos and update Webflow CMS")
    parser.add_argument("--dry-run", action="store_true", help="Preview without updating")
    parser.add_argument("--live", action="store_true", help="Actually update Webflow")
    parser.add_argument("--only-missing", action="store_true", help="Only brands without hero-image")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of brands to process")
    parser.add_argument("--verbose", action="store_true", help="Show detailed scraping info")
    args = parser.parse_args()

    if not args.dry_run and not args.live:
        print("Specify --dry-run or --live")
        return

    dry_run = not args.live

    print("=" * 70, flush=True)
    print("BRAND LOGO SCRAPER", flush=True)
    print("=" * 70, flush=True)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}", flush=True)
    if args.only_missing:
        print("Filter: only brands missing hero-image", flush=True)
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
        brands = [
            b for b in brands
            if not (b.get('fieldData', {}).get('gallery-image-10') or {}).get('url')
        ]
        print(f"Brands missing hero-image: {len(brands)}", flush=True)

    # Apply limit
    if args.limit > 0:
        brands = brands[:args.limit]

    print(f"\nProcessing {len(brands)} brands...", flush=True)
    print("=" * 70, flush=True)

    updated_ids = []
    found_count = 0
    skipped_count = 0

    for i, brand in enumerate(brands, 1):
        item_id = brand['id']
        fd = brand.get('fieldData', {})
        name = fd.get('name', 'Unknown')
        slug = fd.get('slug', '')

        # Check current hero-image
        current_hero = (fd.get('gallery-image-10') or {}).get('url', '')

        print(f"\n[{i}/{len(brands)}] {name} (slug: {slug})", flush=True)

        if current_hero and not args.only_missing:
            if args.verbose:
                print(f"  Already has hero-image: {current_hero[:80]}", flush=True)

        # Resolve brand website URL
        cms_external_link = fd.get('external-link', '') or ''
        brand_url = resolve_brand_url(slug, cms_external_link, shopify_map)

        if not brand_url:
            # No website URL — try Clearbit with guessed domains
            print(f"  No website URL — trying Clearbit with guessed domains...", flush=True)
            logo_url = clearbit_logo_from_guesses(slug, name, verbose=args.verbose)
            if not logo_url:
                print(f"  SKIP — no website and Clearbit guesses failed", flush=True)
                skipped_count += 1
                continue
        else:
            domain = urlparse(brand_url).netloc
            print(f"  Website: {brand_url}", flush=True)

            # Scrape logo from brand website
            logo_url = scrape_logo_from_html(brand_url, verbose=args.verbose)

            # Clearbit fallback if scraping failed or found SVG
            if not logo_url:
                if args.verbose:
                    print(f"  HTML scraping found nothing, trying Clearbit...", flush=True)
                logo_url = clearbit_logo(brand_url, verbose=args.verbose)

            # og:image as last resort (after Clearbit, since og:image is often a promo banner)
            if not logo_url:
                logo_url = scrape_og_image(brand_url, verbose=args.verbose)

        if not logo_url:
            print(f"  NO LOGO FOUND", flush=True)
            skipped_count += 1
            continue

        # Validate the image URL
        if not is_valid_image_url(logo_url):
            if args.verbose:
                print(f"  Image validation failed for {logo_url}", flush=True)
            # Try Clearbit as last resort
            fallback = None
            if brand_url:
                fallback = clearbit_logo(brand_url, verbose=args.verbose)
            if not fallback:
                fallback = clearbit_logo_from_guesses(slug, name, verbose=args.verbose)
            if fallback and is_valid_image_url(fallback):
                logo_url = fallback
            else:
                print(f"  NO VALID LOGO — validation failed", flush=True)
                skipped_count += 1
                continue

        print(f"  LOGO: {logo_url[:80]}", flush=True)
        found_count += 1

        # Update Webflow
        if not dry_run:
            field_data = {'gallery-image-10': {'url': logo_url}}
            if client.update_item(BRANDS_COLLECTION_ID, item_id, field_data):
                print(f"  UPDATED", flush=True)
                updated_ids.append(item_id)
            else:
                print(f"  UPDATE FAILED", flush=True)
            time.sleep(0.5)
        else:
            updated_ids.append(item_id)

        # Delay between brand requests
        time.sleep(2)

    # Publish updated items
    if not dry_run and updated_ids:
        print(f"\n{'='*70}", flush=True)
        print(f"Publishing {len(updated_ids)} updated brands...", flush=True)
        client.publish_items(BRANDS_COLLECTION_ID, updated_ids)

    # Summary
    print(f"\n{'='*70}", flush=True)
    print("SUMMARY", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"Brands processed: {len(brands)}", flush=True)
    print(f"Logos found:      {found_count}", flush=True)
    print(f"Skipped:          {skipped_count}", flush=True)
    print(f"{'Updated' if not dry_run else 'Would update'}: {len(updated_ids)}", flush=True)
    print("\nDone!", flush=True)


if __name__ == "__main__":
    main()
