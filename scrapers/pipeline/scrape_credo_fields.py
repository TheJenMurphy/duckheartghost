#!/usr/bin/env python3
"""
scrape_credo_fields.py

Scrapes Credo Beauty product pages to fill missing CMS fields:
  - ingredients-2 (Ingredients Raw)
  - usage-instructions
  - key-actives
  - shade-count
  - review-number

Note: skin-concerns is handled by a separate scraper.

Each Credo page is fetched once; all fields are extracted in one pass.

Usage:
  python scrape_credo_fields.py              # Dry run
  python scrape_credo_fields.py --write      # Update Webflow
  python scrape_credo_fields.py --limit 10   # Only process 10 items
"""

import os
import re
import sys
import json
import time
import argparse
import requests
from urllib.parse import urlparse, urljoin
from dotenv import load_dotenv

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("ERROR: pip install beautifulsoup4")

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

API_TOKEN = os.environ.get("WEBFLOW_API_TOKEN", "")
API_BASE = "https://api.webflow.com/v2"
COLLECTION_ID = "697d3803e654519eef084068"
WF_HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
    "accept": "application/json",
}

SCRAPE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json",
}

# Fields we're trying to fill (skin-concerns handled by separate scraper)
TARGET_FIELDS = [
    "ingredients-2",
    "usage-instructions",
    "key-actives",
    "shade-count",
    "review-number",
]

rate_limit_remaining = 60


def wf_request(method, url, json_data=None):
    global rate_limit_remaining
    if rate_limit_remaining < 5:
        time.sleep(5)
    resp = requests.request(method, url, headers=WF_HEADERS, json=json_data, timeout=30)
    rate_limit_remaining = int(resp.headers.get("X-RateLimit-Remaining", 60))
    if resp.status_code == 429:
        wait = int(resp.headers.get("Retry-After", 10))
        print(f"  [WF rate limit] waiting {wait}s...")
        time.sleep(wait)
        return wf_request(method, url, json_data)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def fetch_all_items():
    all_items = []
    offset = 0
    while True:
        data = wf_request("GET", f"{API_BASE}/collections/{COLLECTION_ID}/items?limit=100&offset={offset}")
        items = data.get("items", [])
        if not items:
            break
        all_items.extend(items)
        total = data.get("pagination", {}).get("total", 0)
        if len(all_items) >= total:
            break
        offset += 100
        time.sleep(0.2)
    return all_items


# ── Scraping helpers ─────────────────────────────────────────────────

def fetch_credo_html(url):
    """Fetch the product page HTML."""
    try:
        resp = requests.get(url, headers=SCRAPE_HEADERS, timeout=20)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None


def fetch_credo_json(url):
    """Fetch the Shopify JSON endpoint."""
    json_url = url.rstrip("/") + ".json"
    try:
        resp = requests.get(json_url, headers=SCRAPE_HEADERS, timeout=20)
        if resp.status_code == 200:
            return resp.json().get("product", {})
    except Exception:
        pass
    return {}


def extract_ingredients(soup):
    """Extract ingredients from the #ingredients tab."""
    div = soup.find("div", id="ingredients")
    if not div:
        return ""
    # Get all text from the ingredients section
    text = div.get_text(separator=" ", strip=True)
    # Strip product name prefix (everything before "Ingredients:")
    match = re.search(r'Ingredients?\s*:\s*', text, re.I)
    if match:
        text = text[match.end():]
    # Replace || delimiter with commas
    text = re.sub(r'\s*\|\|\s*', ', ', text)
    # Clean up
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) < 10:
        return ""
    return text


def extract_usage(soup):
    """Extract usage instructions from the #howtouse tab."""
    div = soup.find("div", id="howtouse")
    if not div:
        return ""
    paragraphs = div.find_all("p")
    texts = []
    for p in paragraphs:
        t = p.get_text(strip=True)
        # Skip header-like text
        if t.lower() in ("how to use", "directions", ""):
            continue
        texts.append(t)
    result = " ".join(texts).strip()
    if len(result) < 5:
        return ""
    return result


def extract_key_actives(soup):
    """Extract key ingredients from the Overview tab."""
    div = soup.find("div", id="overview")
    if not div:
        return ""
    # Find "Key ingredients" header
    bolds = div.find_all(["p", "span", "strong", "b"])
    for b in bolds:
        if "key ingredient" in b.get_text(strip=True).lower():
            # Get the next sibling paragraph(s)
            next_el = b.find_next_sibling("p")
            if next_el:
                return next_el.get_text(strip=True)
            # Or check parent's next sibling
            parent = b.parent
            if parent:
                next_el = parent.find_next_sibling("p")
                if next_el:
                    return next_el.get_text(strip=True)
    # Alternative: look for detailscontent-p after bold "Key ingredients"
    for p in div.find_all("p", class_="bold"):
        if "key ingredient" in p.get_text(strip=True).lower():
            next_p = p.find_next_sibling("p")
            if next_p:
                return next_p.get_text(strip=True)
    return ""


def extract_concerns_from_tags(tags):
    """Extract skin concerns from Shopify tags."""
    concerns = []
    for tag in tags:
        if tag.startswith("Shop By Concern_"):
            concern = tag.replace("Shop By Concern_", "").strip()
            if concern:
                concerns.append(concern)
    return ", ".join(sorted(set(concerns))) if concerns else ""


def extract_shade_count(product_json):
    """Count color variants (shades) from Shopify JSON."""
    options = product_json.get("options", [])
    variants = product_json.get("variants", [])
    # Check if there's a Color option
    for opt in options:
        name = opt.get("name", "").lower()
        if name in ("color", "colour", "shade"):
            # Count unique color values
            values = opt.get("values", [])
            if values:
                return len(values)
            # Fallback: count variants
            return len(variants)
    return 0


def extract_review_count(html):
    """Extract review count from JSON-LD structured data."""
    try:
        scripts = re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        for script in scripts:
            data = json.loads(script)
            if isinstance(data, list):
                data = data[0]
            rating = data.get("aggregateRating", {})
            if rating:
                count = rating.get("reviewCount", 0)
                return int(count) if count else 0
    except Exception:
        pass
    return 0


def scrape_product(url):
    """Scrape a single Credo product page. Returns dict of extracted fields."""
    result = {}

    # Fetch HTML
    html = fetch_credo_html(url)
    if html:
        soup = BeautifulSoup(html, "html.parser")
        result["ingredients"] = extract_ingredients(soup)
        result["usage"] = extract_usage(soup)
        result["key_actives"] = extract_key_actives(soup)
        result["review_count"] = extract_review_count(html)
    else:
        soup = None
        result["ingredients"] = ""
        result["usage"] = ""
        result["key_actives"] = ""
        result["review_count"] = 0

    # Fetch JSON for tags and variants
    product_json = fetch_credo_json(url)
    if product_json:
        tags = product_json.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        result["skin_concerns"] = extract_concerns_from_tags(tags)
        result["shade_count"] = extract_shade_count(product_json)
    else:
        result["skin_concerns"] = ""
        result["shade_count"] = 0

    return result


def main():
    parser = argparse.ArgumentParser(description="Scrape Credo pages to fill CMS fields")
    parser.add_argument("--write", action="store_true", help="Actually update Webflow")
    parser.add_argument("--limit", type=int, default=0, help="Limit items to process")
    args = parser.parse_args()

    if not API_TOKEN:
        print("Error: WEBFLOW_API_TOKEN not set")
        sys.exit(1)

    print("=" * 65)
    print("Scrape Credo Product Pages → Fill CMS Fields")
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    if args.limit:
        print(f"Limit: {args.limit} items")
    print("=" * 65)

    # 1. Fetch all active items
    print("\n1. Fetching CMS products...")
    all_items = fetch_all_items()
    active = [i for i in all_items if not i.get("isArchived", False)]
    print(f"  Active items: {len(active)}")

    # 2. Identify items needing data
    needs_scraping = []
    for item in active:
        fd = item.get("fieldData", {})
        url = fd.get("external-link", "")
        if not url or "credobeauty.com" not in url:
            continue

        missing = []
        if not fd.get("ingredients-2", "").strip():
            missing.append("ingredients-2")
        if not fd.get("usage-instructions", "").strip():
            missing.append("usage-instructions")
        if not fd.get("key-actives", "").strip():
            missing.append("key-actives")
        if not fd.get("shade-count"):
            missing.append("shade-count")
        if not fd.get("review-number"):
            missing.append("review-number")

        if missing:
            needs_scraping.append({
                "id": item["id"],
                "name": fd.get("name", ""),
                "brand": fd.get("brand-name", ""),
                "url": url,
                "missing": missing,
                "existing": fd,
            })

    print(f"  Need scraping: {needs_scraping.__len__()}")

    if args.limit:
        needs_scraping = needs_scraping[:args.limit]
        print(f"  Processing: {len(needs_scraping)} (limited)")

    # 3. Scrape and collect updates
    print(f"\n2. Scraping {len(needs_scraping)} Credo product pages...\n")
    updates = []
    scrape_errors = 0
    fields_found = {f: 0 for f in TARGET_FIELDS}

    for i, item in enumerate(needs_scraping, 1):
        try:
            scraped = scrape_product(item["url"])

            patch = {}
            # Only update fields that are missing AND we found data for
            if "ingredients-2" in item["missing"] and scraped["ingredients"]:
                patch["ingredients-2"] = f"<p>{scraped['ingredients']}</p>"
                fields_found["ingredients-2"] += 1

            if "usage-instructions" in item["missing"] and scraped["usage"]:
                patch["usage-instructions"] = f"<p>{scraped['usage']}</p>"
                fields_found["usage-instructions"] += 1

            if "key-actives" in item["missing"] and scraped["key_actives"]:
                patch["key-actives"] = scraped["key_actives"]
                fields_found["key-actives"] += 1

            if "shade-count" in item["missing"] and scraped["shade_count"] > 0:
                patch["shade-count"] = scraped["shade_count"]
                fields_found["shade-count"] += 1

            if "review-number" in item["missing"] and scraped["review_count"] > 0:
                patch["review-number"] = scraped["review_count"]
                fields_found["review-number"] += 1

            if patch:
                updates.append({
                    "id": item["id"],
                    "name": item["name"],
                    "brand": item["brand"],
                    "patch": patch,
                })

            if i % 25 == 0 or i == len(needs_scraping):
                print(f"  [{i}/{len(needs_scraping)}] scraped... (last: {item['name'][:40]})")

            time.sleep(0.5)  # Be polite to Credo's servers

        except Exception as e:
            print(f"  [{i}/{len(needs_scraping)}] SCRAPE ERROR: {item['name'][:35]} -> {e}")
            scrape_errors += 1
            time.sleep(1)

    print(f"\n  Fields found across all pages:")
    for field, count in sorted(fields_found.items(), key=lambda x: -x[1]):
        print(f"    {field:25s} {count:>4}")

    # 4. Apply updates
    print(f"\n3. Applying {len(updates)} updates...\n")
    updated = 0
    wf_errors = 0

    for i, u in enumerate(updates, 1):
        if args.write:
            try:
                wf_request(
                    "PATCH",
                    f"{API_BASE}/collections/{COLLECTION_ID}/items/{u['id']}",
                    json_data={"fieldData": u["patch"]},
                )
                updated += 1
                if i % 25 == 0 or i == len(updates):
                    fields_str = ", ".join(u["patch"].keys())
                    print(f"  [{i}/{len(updates)}] {u['name'][:35]} -> {fields_str}")
                time.sleep(0.3)
            except Exception as e:
                print(f"  [{i}/{len(updates)}] WF ERROR: {u['name'][:35]} -> {e}")
                wf_errors += 1
                time.sleep(1)
        else:
            fields_str = ", ".join(u["patch"].keys())
            preview = ""
            if "shade-count" in u["patch"]:
                preview += f" shades={u['patch']['shade-count']}"
            if "review-number" in u["patch"]:
                preview += f" reviews={u['patch']['review-number']}"
            print(f"  {u['brand'][:12]:12s} | {u['name'][:35]:35s} -> {fields_str}{preview}")
            updated += 1

    print(f"\n{'='*65}")
    print("SUMMARY")
    print(f"  Pages scraped:  {len(needs_scraping)}")
    print(f"  Items updated:  {updated}")
    print(f"  Scrape errors:  {scrape_errors}")
    print(f"  Webflow errors: {wf_errors}")
    print(f"\n  Fields filled:")
    for field, count in sorted(fields_found.items(), key=lambda x: -x[1]):
        print(f"    {field:25s} {count:>4}")
    print(f"{'='*65}")

    if not args.write and updated > 0:
        print(f"\n  Run with --write to apply:")
        print(f"  python scrape_credo_fields.py --write")


if __name__ == "__main__":
    main()
