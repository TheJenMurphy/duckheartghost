#!/usr/bin/env python3
"""
Scrape all brands from Credo Beauty and push to Webflow Brands collection.

Uses Playwright (headless browser) because Credo has bot protection.
Uses Anthropic Claude to enrich brand data with structured fields.

Usage:
    python3 scrape_credo_brands.py                    # Dry run (scrape only, no push)
    python3 scrape_credo_brands.py --push              # Scrape + push to Webflow
    python3 scrape_credo_brands.py --push --limit 5    # Push first 5 only
    python3 scrape_credo_brands.py --from-cache        # Use cached JSON, skip scraping
    python3 scrape_credo_brands.py --from-cache --push # Push from cache
"""

import os
import re
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

import requests

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    sys.exit("ERROR: pip install playwright && python -m playwright install chromium")

try:
    import anthropic
except ImportError:
    print("WARNING: pip install anthropic — AI enrichment will be skipped")
    anthropic = None

# ─── Config ──────────────────────────────────────────────────────────────────

WEBFLOW_API_BASE = "https://api.webflow.com/v2"
BRANDS_COLLECTION_ID = "697d981be773ae7dbfc093ed"
CREDO_BASE = "https://credobeauty.com"
CACHE_FILE = Path(__file__).parent / "data" / "credo_brands_cache.json"

# ─── Webflow helpers ─────────────────────────────────────────────────────────

rate_limit_remaining = 60


def wf_headers():
    token = os.environ.get("WEBFLOW_API_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "accept": "application/json",
    }


def wf_request(method, url, json_data=None):
    global rate_limit_remaining
    if rate_limit_remaining < 5:
        time.sleep(5)
    resp = requests.request(method, url, headers=wf_headers(), json=json_data, timeout=30)
    rate_limit_remaining = int(resp.headers.get("X-RateLimit-Remaining", 60))
    if resp.status_code == 429:
        wait = int(resp.headers.get("Retry-After", 10))
        print(f"  [rate limit] waiting {wait}s...")
        time.sleep(wait)
        return wf_request(method, url, json_data)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def get_existing_brands() -> Dict[str, Dict]:
    """Fetch all existing brands from Webflow, keyed by slug."""
    brands = {}
    offset = 0
    while True:
        url = f"{WEBFLOW_API_BASE}/collections/{BRANDS_COLLECTION_ID}/items?limit=100&offset={offset}"
        data = wf_request("GET", url)
        items = data.get("items", [])
        for item in items:
            slug = item.get("fieldData", {}).get("slug", "")
            if slug:
                brands[slug] = item
        if len(items) < 100:
            break
        offset += 100
        time.sleep(0.5)
    return brands


def upsert_brand(slug: str, field_data: Dict, existing: Dict[str, Dict]) -> bool:
    """Create or update a brand in Webflow."""
    if slug in existing:
        item_id = existing[slug]["id"]
        url = f"{WEBFLOW_API_BASE}/collections/{BRANDS_COLLECTION_ID}/items/{item_id}"
        payload = {"isArchived": False, "isDraft": False, "fieldData": field_data}
        try:
            wf_request("PATCH", url, payload)
            return True
        except Exception as e:
            print(f"    Update failed: {e}")
            return False
    else:
        url = f"{WEBFLOW_API_BASE}/collections/{BRANDS_COLLECTION_ID}/items"
        payload = {"isArchived": False, "isDraft": False, "fieldData": field_data}
        try:
            wf_request("POST", url, payload)
            return True
        except Exception as e:
            print(f"    Create failed: {e}")
            return False


# ─── Playwright scraping ─────────────────────────────────────────────────────

SALE_SUFFIX = "-friends-of-credo-sale"


def safe_goto(page, url, timeout=60000):
    """Navigate to URL with domcontentloaded (faster than networkidle)."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        time.sleep(3)
        return True
    except PlaywrightTimeout:
        print(f"    Timeout loading {url}")
        return False
    except Exception as e:
        print(f"    Error loading {url}: {e}")
        return False


def fetch_all_collections_json(page) -> List[Dict]:
    """Fetch all collections from Shopify JSON API (paginated)."""
    all_collections = []
    pg = 1
    while True:
        url = f"{CREDO_BASE}/collections.json?limit=250&page={pg}"
        if not safe_goto(page, url, timeout=45000):
            break
        try:
            body = page.query_selector("body, pre")
            raw = body.inner_text()
            data = json.loads(raw)
            batch = data.get("collections", [])
            all_collections.extend(batch)
            print(f"    Page {pg}: {len(batch)} collections")
            if len(batch) < 250:
                break
            pg += 1
        except (json.JSONDecodeError, Exception) as e:
            print(f"    Page {pg} failed: {e}")
            break
    return all_collections


def filter_brand_collections(collections: List[Dict]) -> List[Dict]:
    """
    Filter brand collections from all Shopify collections.

    Key heuristic: Every Credo brand has a matching
    "{handle}-friends-of-credo-sale" collection. We use this to
    reliably identify brand handles out of 700+ total collections.
    """
    # Build set of all handles
    all_handles = {c["handle"] for c in collections}

    # Find brand handles: those that have a matching sale collection
    sale_handles = {h for h in all_handles if h.endswith(SALE_SUFFIX)}
    brand_handles = set()
    for sale_handle in sale_handles:
        base = sale_handle[: -len(SALE_SUFFIX)]
        if base in all_handles:
            brand_handles.add(base)

    # Build handle → collection lookup
    col_by_handle = {c["handle"]: c for c in collections}

    brands = []
    for handle in sorted(brand_handles):
        col = col_by_handle[handle]
        title = col.get("title", handle.replace("-", " ").title())

        # Strip trailing suffixes from Credo display names
        # e.g. "ILIA Beauty" → "ILIA", "Kosas Makeup & Skincare" → "Kosas"
        clean_name = re.sub(
            r'\s+(Makeup & Skincare|Skin care & Beauty|Skincare & Beauty|'
            r'Makeup|Skincare|Skin care|Cosmetics|Beauty|Products|'
            r'Hair Care|Natural Deodorant|Hand Soap|Organics|Parfum|Baby)\s*$',
            '', title, flags=re.IGNORECASE
        ).strip()
        # Second pass for double suffixes like "Olio E Osso Skin care"
        clean_name = re.sub(
            r'\s+(Skin care|Skincare|Makeup|Beauty|Products)\s*$',
            '', clean_name, flags=re.IGNORECASE
        ).strip()

        # Get image URL
        img = col.get("image", {})
        img_url = ""
        if img and img.get("src"):
            img_url = img["src"]
            if img_url.startswith("//"):
                img_url = "https:" + img_url

        # Get description from body_html
        body_html = col.get("body_html", "") or ""
        description = ""
        if body_html:
            plain = re.sub(r'<[^>]+>', ' ', body_html)
            plain = re.sub(r'\s+', ' ', plain).strip()
            if len(plain) > 10:
                description = plain

        brands.append({
            "name": clean_name or title,
            "slug": handle,
            "credo_url": f"{CREDO_BASE}/collections/{handle}",
            "logo_url": img_url,
            "description": description,
        })

    return brands


def scrape_brand_list(page) -> List[Dict]:
    """Scrape all brand names and URLs from Credo's brands directory."""
    print("\n" + "=" * 70)
    print("STEP 1: Scraping brand list from Credo Beauty")
    print("=" * 70)

    # Fetch all collections via Shopify JSON API
    print("\n  Fetching all collections from Shopify JSON API...")
    all_collections = fetch_all_collections_json(page)

    if not all_collections:
        print("    ERROR: Could not fetch collections. Try --headed to debug.")
        return []

    print(f"\n  Total collections fetched: {len(all_collections)}")

    # Filter to brands only using the friends-of-credo-sale heuristic
    brands = filter_brand_collections(all_collections)
    print(f"  Brands identified: {len(brands)}")

    if brands:
        for b in brands[:10]:
            has_img = " [img]" if b.get("logo_url") else ""
            has_desc = " [desc]" if b.get("description") else ""
            print(f"    - {b['name']}{has_img}{has_desc}")
        if len(brands) > 10:
            print(f"    ... and {len(brands) - 10} more")

    return brands


def scrape_brand_page(page, brand: Dict) -> Dict:
    """Scrape a single brand's Credo collection page for details."""
    slug = brand["slug"]
    data = {**brand}

    # Try Shopify collection JSON first (faster, more structured)
    json_url = f"{CREDO_BASE}/collections/{slug}.json"
    if safe_goto(page, json_url, timeout=30000):
        try:
            body = page.query_selector("body, pre")
            if body:
                raw = body.inner_text()
                col_data = json.loads(raw).get("collection", {})
                if col_data:
                    title = col_data.get("title", "")
                    if title:
                        data["name"] = title
                    body_html = col_data.get("body_html", "")
                    if body_html:
                        # Strip HTML tags for plain text description
                        plain = re.sub(r'<[^>]+>', ' ', body_html)
                        plain = re.sub(r'\s+', ' ', plain).strip()
                        if len(plain) > 20:
                            data["description"] = plain
                    img = col_data.get("image", {})
                    if img and img.get("src"):
                        src = img["src"]
                        if src.startswith("//"):
                            src = "https:" + src
                        data["logo_url"] = src
        except (json.JSONDecodeError, Exception):
            pass

    # Also load the HTML page for additional data
    html_url = brand["credo_url"]
    if safe_goto(page, html_url, timeout=30000):
        # Get the Credo display name from h1 (stored separately, don't override cleaned name)
        try:
            h1 = page.query_selector("h1")
            if h1:
                page_title = h1.inner_text().strip()
                if page_title and len(page_title) < 200:
                    data["credo_display_name"] = page_title
        except Exception:
            pass

        # Get meta description
        try:
            meta = page.query_selector('meta[name="description"]')
            if meta:
                desc = meta.get_attribute("content") or ""
                if desc.strip():
                    data["meta_description"] = desc.strip()
        except Exception:
            pass

        # Get brand description from page content (if not from JSON)
        if not data.get("description"):
            try:
                desc_selectors = [
                    ".collection-description",
                    ".collection-hero__description",
                    '[class*="collection-description"]',
                    '[class*="brand-description"]',
                    '[class*="brand-story"]',
                    ".rte",
                ]
                for sel in desc_selectors:
                    desc_el = page.query_selector(sel)
                    if desc_el:
                        text = desc_el.inner_text().strip()
                        if text and len(text) > 20:
                            data["description"] = text
                            break
            except Exception:
                pass

        # Get brand logo/image (if not from JSON)
        if not data.get("logo_url"):
            try:
                logo_selectors = [
                    ".collection-hero img",
                    '[class*="brand-logo"] img',
                    '[class*="collection-image"] img',
                    ".collection-hero__image img",
                    ".collection__image img",
                    ".collection-banner img",
                ]
                for sel in logo_selectors:
                    img = page.query_selector(sel)
                    if img:
                        src = img.get_attribute("src") or img.get_attribute("data-src") or ""
                        if src and not src.startswith("data:"):
                            if src.startswith("//"):
                                src = "https:" + src
                            data["logo_url"] = src
                            break
            except Exception:
                pass

        # Count products on the page
        try:
            product_cards = page.query_selector_all(
                '[class*="product-card"], [class*="product-grid"] > *, '
                '.grid-item, .collection-product, [class*="ProductCard"]'
            )
            if product_cards:
                data["product_count"] = len(product_cards)

            count_el = page.query_selector('[class*="product-count"], [class*="results-count"]')
            if count_el:
                count_text = count_el.inner_text()
                numbers = re.findall(r'\d+', count_text)
                if numbers:
                    data["product_count"] = int(numbers[0])
        except Exception:
            pass

        # Try to find the brand's own website link
        try:
            all_links = page.query_selector_all("a")
            for link in all_links:
                href = link.get_attribute("href") or ""
                text = (link.inner_text() or "").strip().lower()
                if any(kw in text for kw in ["visit", "website", "shop", "official"]):
                    if href.startswith("http") and "credobeauty" not in href:
                        data["website"] = href
                        break
        except Exception:
            pass

    return data


# ─── AI enrichment ───────────────────────────────────────────────────────────

def enrich_with_ai(brands: List[Dict]) -> List[Dict]:
    """Use Claude to enrich brand data with structured fields."""
    if not anthropic:
        print("\n  Anthropic not installed — skipping AI enrichment")
        return brands

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("\n  No ANTHROPIC_API_KEY — skipping AI enrichment")
        return brands

    print("\n" + "=" * 70)
    print("STEP 3: AI enrichment with Claude")
    print("=" * 70)

    client = anthropic.Anthropic(api_key=api_key)

    # Process in batches of 10 to minimize API calls
    batch_size = 10
    enriched = []

    for i in range(0, len(brands), batch_size):
        batch = brands[i:i + batch_size]
        batch_names = [b["name"] for b in batch]
        print(f"\n  Enriching batch {i // batch_size + 1}: {', '.join(batch_names[:5])}{'...' if len(batch_names) > 5 else ''}")

        # Build context about each brand in the batch
        brand_context = ""
        for b in batch:
            brand_context += f"\n--- {b['name']} ---\n"
            if b.get("description"):
                brand_context += f"Credo description: {b['description'][:500]}\n"
            if b.get("meta_description"):
                brand_context += f"Meta: {b['meta_description'][:300]}\n"
            if b.get("website"):
                brand_context += f"Website: {b['website']}\n"

        prompt = f"""You are a clean beauty industry expert. For each brand below, provide structured data in JSON format.
Return a JSON array with one object per brand. Each object should have the brand name as key "name" and these fields:

- "tagline": Brand tagline or mission statement (1 sentence, empty string if unknown)
- "founder": Founder name(s) (empty string if unknown)
- "founded_year": Year founded (null if unknown)
- "headquarters": "City, State" or "City, Country" (empty string if unknown)
- "parent_company": Parent company name if acquired (empty string if independent/unknown)
- "ownership": One of: "Independent", "Conglomerate", "Private", "Public" (best guess)
- "certifications": Comma-separated list of certifications like "B Corp, Leaping Bunny, EWG Verified, USDA Organic, ECOCERT, Climate Neutral, 1% for the Planet, MADE SAFE, Peta" (empty string if unknown)
- "price_range": Approximate price range like "$15-$65" (empty string if unknown)
- "best_seller": Their most popular/iconic product name (empty string if unknown)

Only include data you're confident about. Use empty strings for unknowns.

Brands:
{brand_context}

Return ONLY the JSON array, no other text."""

        try:
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = message.content[0].text.strip()

            # Extract JSON from response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                ai_data = json.loads(json_match.group())
            else:
                ai_data = json.loads(response_text)

            # Merge AI data back into brands
            ai_by_name = {}
            for item in ai_data:
                n = item.get("name", "")
                ai_by_name[n.lower()] = item

            for b in batch:
                ai = ai_by_name.get(b["name"].lower(), {})
                if ai:
                    for key in ["tagline", "founder", "founded_year", "headquarters",
                                "parent_company", "ownership", "certifications",
                                "price_range", "best_seller"]:
                        val = ai.get(key)
                        if val and val != "" and val is not None:
                            b[f"ai_{key}"] = val
                enriched.append(b)

            print(f"    Enriched {len(batch)} brands")
            time.sleep(1)  # Rate limit

        except Exception as e:
            print(f"    AI enrichment failed: {e}")
            enriched.extend(batch)

    return enriched


# ─── Build Webflow field data ────────────────────────────────────────────────

def brand_to_webflow_fields(brand: Dict) -> Dict:
    """Convert scraped brand data to Webflow field data."""
    fields = {
        "name": brand["name"][:100],
        "slug": brand["slug"],
    }

    # Description (RichText)
    desc = brand.get("description") or brand.get("meta_description") or ""
    if desc:
        # Clean up and wrap in HTML
        desc = desc.replace("\n", "<br>")
        fields["what-it-is-2"] = f"<p>{desc}</p>"

    # Tagline
    tagline = brand.get("ai_tagline", "")
    if tagline:
        fields["tagline"] = tagline[:256]

    # Hero logo (Image field)
    logo = brand.get("logo_url", "")
    if logo:
        fields["gallery-image-10"] = {"url": logo}

    # Card type
    fields["card-type"] = "Brand"

    # Founder
    founder = brand.get("ai_founder", "")
    founded_year = brand.get("ai_founded_year")
    if founder and founded_year:
        fields["founder"] = f"{founder} ({founded_year})"
    elif founder:
        fields["founder"] = founder
    elif founded_year:
        fields["founder"] = f"({founded_year})"

    # Headquarters / Parent Co
    hq = brand.get("ai_headquarters", "")
    if hq:
        fields["headquaters"] = hq  # Note: typo in Webflow field slug

    # Parent company / Conflict of Interest
    parent = brand.get("ai_parent_company", "")
    if parent:
        fields["parent-company"] = parent

    # Certifications
    certs = brand.get("ai_certifications", "")
    if certs:
        fields["certifications"] = certs[:256]

    # Price range
    price = brand.get("ai_price_range", "")
    if price:
        fields["price-range"] = price

    # Best seller
    best = brand.get("ai_best_seller", "")
    if best:
        fields["best-seller"] = best[:256]

    # Product count (from Credo page)
    count = brand.get("product_count")
    if count and isinstance(count, int):
        fields["product-count"] = count

    # External link (brand's own website)
    website = brand.get("website", "")
    if website:
        fields["external-link"] = website

    # Affiliate link (Credo page)
    fields["affiliate-url"] = brand.get("credo_url", "")

    # Remove empty/None values
    return {k: v for k, v in fields.items() if v is not None and v != ""}


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape Credo Beauty brands")
    parser.add_argument("--push", action="store_true", help="Push to Webflow (default: dry run)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of brands to process")
    parser.add_argument("--from-cache", action="store_true", help="Use cached JSON instead of scraping")
    parser.add_argument("--skip-ai", action="store_true", help="Skip AI enrichment")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode (visible)")
    args = parser.parse_args()

    print("=" * 70)
    print("CREDO BEAUTY BRAND SCRAPER")
    print("=" * 70)
    print(f"Mode: {'PUSH TO WEBFLOW' if args.push else 'DRY RUN'}")
    if args.limit:
        print(f"Limit: {args.limit}")

    brands = []

    if args.from_cache and CACHE_FILE.exists():
        print(f"\nLoading from cache: {CACHE_FILE}")
        with open(CACHE_FILE) as f:
            brands = json.load(f)
        print(f"  Loaded {len(brands)} brands")
    else:
        # Step 1 & 2: Scrape with Playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not args.headed)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            # Step 1: Get brand list
            brands = scrape_brand_list(page)

            if not brands:
                print("\nERROR: Could not find any brands. Try --headed to debug.")
                browser.close()
                return

            # Step 2: Scrape each brand page
            print("\n" + "=" * 70)
            print("STEP 2: Scraping individual brand pages")
            print("=" * 70)

            limit = args.limit if args.limit > 0 else len(brands)
            brands = brands[:limit]

            for i, brand in enumerate(brands):
                print(f"\n  [{i + 1}/{len(brands)}] {brand['name']}...")
                brand.update(scrape_brand_page(page, brand))

                # Brief summary
                fields_found = [k for k in ["description", "meta_description", "logo_url",
                                             "product_count", "website"] if brand.get(k)]
                print(f"    Found: {', '.join(fields_found) if fields_found else 'basic info only'}")

                time.sleep(0.5)  # Be polite

            browser.close()

        # Save cache
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(brands, f, indent=2)
        print(f"\n  Saved cache: {CACHE_FILE}")

    # Step 3: AI enrichment
    if not args.skip_ai:
        brands = enrich_with_ai(brands)

    # Step 4: Push to Webflow
    print("\n" + "=" * 70)
    print(f"STEP 4: {'Pushing to Webflow' if args.push else 'Preview (dry run)'}")
    print("=" * 70)

    existing = {}
    if args.push:
        print("\n  Fetching existing brands from Webflow...")
        existing = get_existing_brands()
        print(f"  Found {len(existing)} existing brands")

    created = 0
    updated = 0
    skipped = 0

    for brand in brands:
        fields = brand_to_webflow_fields(brand)
        slug = fields.get("slug", "")

        if args.push:
            action = "update" if slug in existing else "create"
            print(f"  [{action.upper()}] {fields.get('name', slug)}")
            if upsert_brand(slug, fields, existing):
                if action == "update":
                    updated += 1
                else:
                    created += 1
            else:
                skipped += 1
            time.sleep(0.5)
        else:
            action = "would update" if slug in existing else "would create"
            print(f"  [{action.upper()}] {fields.get('name', slug)}")
            filled = [k for k, v in fields.items() if v and k not in ("name", "slug", "card-type")]
            print(f"    Fields: {', '.join(filled)}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total brands scraped: {len(brands)}")
    if args.push:
        print(f"  Created: {created}")
        print(f"  Updated: {updated}")
        print(f"  Failed: {skipped}")
    else:
        print("  (Dry run — no changes made. Use --push to write to Webflow)")

    # Print field coverage stats
    field_counts = {}
    for brand in brands:
        fields = brand_to_webflow_fields(brand)
        for k, v in fields.items():
            if v and k not in ("name", "slug", "card-type"):
                field_counts[k] = field_counts.get(k, 0) + 1

    if field_counts:
        print("\n  Field coverage:")
        for field, count in sorted(field_counts.items(), key=lambda x: -x[1]):
            pct = count / len(brands) * 100
            print(f"    {field:30s} {count:4d}/{len(brands)} ({pct:.0f}%)")


if __name__ == "__main__":
    main()
