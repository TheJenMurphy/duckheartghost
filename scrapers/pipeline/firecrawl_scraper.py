#!/usr/bin/env python3
"""
firecrawl_scraper.py

FireCrawl-powered scraper for Credo Beauty product pages.
Single product mode: 1 API call (1 credit) → 10 fields via regex.
Batch mode: pull product URLs from Webflow CMS collections, then FireCrawl each one.

Usage:
  # Single product
  python firecrawl_scraper.py --demo
  python firecrawl_scraper.py https://credobeauty.com/products/the-silk-cream
  python firecrawl_scraper.py --demo --json-mode          # AI extraction (+4 credits)

  # Batch — all three collections (makeups, skincares, tools)
  python firecrawl_scraper.py --batch
  python firecrawl_scraper.py --batch --collection makeups
  python firecrawl_scraper.py --batch --collection skincares,tools
  python firecrawl_scraper.py --batch --limit 5           # 5 per collection
  python firecrawl_scraper.py --batch --dry-run            # list products, no scraping
"""

import os
import re
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

try:
    from firecrawl import FirecrawlApp
except ImportError:
    sys.exit("ERROR: pip install firecrawl-py")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
WEBFLOW_API_TOKEN = os.environ.get("WEBFLOW_API_TOKEN", "")
WEBFLOW_API_BASE = "https://api.webflow.com/v2"

DEMO_URL = "https://credobeauty.com/products/the-silk-cream"

# Webflow CMS collection IDs (same as other scrapers)
WF_COLLECTIONS = {
    "makeups":   "697d3803e654519eef084068",
    "skincares": "697d723c3df8451b1f1cce1a",
    "tools":     "697d7d4a824e85c10e862dd1",
}

ALL_COLLECTIONS = list(WF_COLLECTIONS.keys())

# Output directory for batch results
DATA_DIR = Path(__file__).parent / "data" / "firecrawl"

FIELDS = [
    "product_name", "brand", "price", "description", "ingredients",
    "product_type", "images", "tags", "benefits", "skin_types",
]

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "product_name": {"type": "string"},
        "brand": {"type": "string"},
        "price": {"type": "string"},
        "description": {"type": "string"},
        "ingredients": {"type": "string"},
        "product_type": {"type": "string"},
        "images": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "benefits": {"type": "array", "items": {"type": "string"}},
        "skin_types": {"type": "array", "items": {"type": "string"}},
    },
}


# ---------------------------------------------------------------------------
# Webflow CMS — pull products with their Credo URLs
# ---------------------------------------------------------------------------
rate_limit_remaining = 60


def wf_request(method, url, json_data=None):
    """Webflow API request with rate-limit handling."""
    global rate_limit_remaining
    if rate_limit_remaining < 5:
        time.sleep(5)
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
        "Content-Type": "application/json",
        "accept": "application/json",
    }
    resp = requests.request(method, url, headers=headers, json=json_data, timeout=30)
    rate_limit_remaining = int(resp.headers.get("X-RateLimit-Remaining", 60))
    if resp.status_code == 429:
        wait = int(resp.headers.get("Retry-After", 10))
        print(f"  [WF rate limit] waiting {wait}s...")
        time.sleep(wait)
        return wf_request(method, url, json_data)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def fetch_webflow_products(collection_id):
    """Fetch all items from a Webflow collection. Returns list of fieldData dicts."""
    all_items = []
    offset = 0
    while True:
        try:
            data = wf_request("GET", f"{WEBFLOW_API_BASE}/collections/{collection_id}/items?limit=100&offset={offset}")
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                print(f"collection {collection_id} not found (404), skipping")
                return []
            raise
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


def get_products_for_collection(collection_name):
    """Get Credo product URLs from a Webflow collection.
    Returns list of dicts: [{name, brand, url, slug, wf_id}, ...]
    """
    cid = WF_COLLECTIONS[collection_name]
    items = fetch_webflow_products(cid)

    products = []
    for item in items:
        if item.get("isArchived", False):
            continue
        fd = item.get("fieldData", {})
        url = fd.get("external-link", "")
        if not url or "credobeauty.com" not in url:
            continue
        products.append({
            "name": fd.get("name", ""),
            "brand": fd.get("brand-name", ""),
            "url": url.rstrip("/"),
            "slug": fd.get("slug", ""),
            "wf_id": item.get("id", ""),
        })
    return products


# ---------------------------------------------------------------------------
# Regex / text extractors  (run locally — zero API credits)
# ---------------------------------------------------------------------------
def extract_product_name(md, meta):
    og = (meta.get("og:title") or meta.get("title") or "").strip()
    if og:
        for sep in [" | ", " - ", " – ", " — "]:
            if sep in og:
                parts = og.split(sep)
                return max(parts, key=len).strip()
        return og
    m = re.search(r"^#{1,2}\s+(.+)", md, re.MULTILINE)
    return m.group(1).strip() if m else None


def extract_brand(md, meta):
    for key in ["og:site_name", "twitter:site"]:
        val = (meta.get(key) or "").strip()
        if val and val.lower() not in ("credo beauty", "credo", "@credobeauty"):
            return val
    m = re.search(r"(?:brand|vendor|by)\s*[:\-–]\s*(.+)", md, re.IGNORECASE)
    if m:
        return m.group(1).strip().split("\n")[0].strip()
    m = re.search(r'"brand"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', md)
    if m:
        return m.group(1).strip()
    m = re.search(r'"brand"\s*:\s*"([^"]+)"', md)
    if m:
        return m.group(1).strip()
    return None


def extract_price(md, meta):
    for key in ("og:price:amount", "product:price:amount", "price"):
        val = (meta.get(key) or "").strip()
        if val:
            return f"${val}" if not val.startswith("$") else val
    m = re.search(r"\$\d+(?:\.\d{2})?", md)
    return m.group(0) if m else None


def extract_description(md, meta):
    og = (meta.get("og:description") or meta.get("description") or "").strip()
    if og and len(og) > 20:
        return og
    m = re.search(
        r"(?:description|about|details)\s*\n+(.+?)(?:\n#{1,3}\s|\n\*\*|$)",
        md, re.IGNORECASE | re.DOTALL,
    )
    if m:
        text = m.group(1).strip()
        if len(text) > 20:
            return text[:500]
    return og if og else None


def extract_ingredients(md, meta):
    patterns = [
        r"(?:#{1,3}\s*)?ingredients\s*[:\n]+\s*(.+?)(?:\n#{1,3}\s|\n\*\*[A-Z]|\Z)",
        r"full\s+ingredient\s+list\s*[:\n]+\s*(.+?)(?:\n#{1,3}\s|\n\*\*[A-Z]|\Z)",
        r"((?:aqua|water)\s*[\(/].*?(?:,\s*\w+){5,}.*?)(?:\n\n|\n#{1,3}\s|\Z)",
    ]
    for pat in patterns:
        m = re.search(pat, md, re.IGNORECASE | re.DOTALL)
        if m:
            text = m.group(1).strip()
            text = re.sub(r"\*+", "", text)
            text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
            text = text.strip().rstrip(".")
            if len(text) > 10:
                return text
    return None


def extract_product_type(md, meta):
    for key in ("og:type", "product:category", "category"):
        val = (meta.get(key) or "").strip()
        if val and val.lower() not in ("product", "website"):
            return val
    m = re.search(r"(?:home|shop)\s*[>/»]\s*(.+?)(?:\s*[>/»]|$)", md, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    categories = [
        "moisturizer", "serum", "cleanser", "toner", "mask", "oil",
        "sunscreen", "spf", "eye cream", "lip", "foundation", "concealer",
        "blush", "bronzer", "mascara", "shampoo", "conditioner", "body",
    ]
    md_lower = md[:2000].lower()
    for cat in categories:
        if cat in md_lower:
            return cat.title()
    return None


def extract_images(md, meta):
    images = []
    og_img = (meta.get("og:image") or "").strip()
    if og_img:
        images.append(og_img)
    for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", md):
        url = m.group(1).strip()
        if url not in images and "logo" not in url.lower():
            images.append(url)
    for m in re.finditer(r"(https://cdn\.shopify\.com/s/files/[^\s\"')]+)", md):
        url = m.group(1).strip()
        if url not in images:
            images.append(url)
    return images if images else None


def extract_tags(md, meta):
    tag_keywords = [
        "clean", "vegan", "cruelty-free", "cruelty free", "organic",
        "gluten-free", "gluten free", "fragrance-free", "fragrance free",
        "paraben-free", "paraben free", "sulfate-free", "sulfate free",
        "phthalate-free", "phthalate free", "non-toxic", "nontoxic",
        "reef-safe", "reef safe", "ewg verified",
        "biodegradable", "recyclable", "sustainable", "fair trade",
        "dermatologist tested", "hypoallergenic", "non-comedogenic",
        "leaping bunny", "b corp", "certified",
    ]
    found = []
    md_lower = md.lower()
    for tag in tag_keywords:
        if tag in md_lower:
            normalized = tag.replace("-", "-").title()
            if normalized not in found:
                found.append(normalized)
    return found if found else None


def extract_benefits(md, meta):
    found = []

    # Credo format: "Why We Love It:" or "Why we stand behind it"
    m = re.search(
        r"(?:why we (?:love it|stand behind it))\s*[:\n]+\s*(.+?)(?:\n\n\*\*|\n#{1,3}\s|\Z)",
        md, re.IGNORECASE | re.DOTALL,
    )
    if m:
        text = m.group(1).strip()
        if len(text) > 10:
            found.append(text[:500])

    # Credo format: "This Product Is:" description
    m = re.search(
        r"\*\*this product is:?\*\*\s*(.+?)(?:\n\n\*\*|\n#{1,3}\s|\Z)",
        md, re.IGNORECASE | re.DOTALL,
    )
    if m:
        text = m.group(1).strip()
        if len(text) > 10:
            found.append(text[:500])

    # Credo highlights: key ingredient descriptions (e.g. "Copper Peptides - Supports collagen")
    # Only look in the first half of the page (avoid nav/footer junk)
    product_section = md[:len(md) // 2]
    for m in re.finditer(r"([A-Z][\w\s]{2,25}?)\s*[-–—]\s*([A-Z][^[\n]{10,80})", product_section):
        text = m.group(2).strip()
        # Skip if it contains URLs or navigation patterns
        if "http" in text or "credobeauty" in text or "](" in text:
            continue
        ingredient_benefit = f"{m.group(1).strip()}: {text}"
        if ingredient_benefit not in found:
            found.append(ingredient_benefit)
        if len(found) >= 6:
            break

    # Fallback: generic "Benefits" section
    if not found:
        m = re.search(
            r"(?:#{1,3}\s*)?(?:benefits|key benefits|what it does)\s*[:\n]+\s*(.+?)(?:\n#{1,3}\s|\n\*\*[A-Z]|\Z)",
            md, re.IGNORECASE | re.DOTALL,
        )
        if m:
            text = m.group(1).strip()
            items = re.split(r"\n\s*[-*•]\s*", text)
            items = [i.strip() for i in items if i.strip() and len(i.strip()) > 3]
            if items:
                found = items

    return found if found else None


def extract_skin_types(md, meta):
    skin_types = [
        "all skin types", "dry", "oily", "combination", "sensitive",
        "normal", "mature", "acne-prone", "acne prone",
    ]
    found = []
    md_lower = md.lower()

    # Credo format: "Suitable for\n\nAll skin types, especially dry."
    m = re.search(r"suitable for\s*\n+(.{0,200})", md_lower)
    if m:
        context = m.group(1)
        for st in skin_types:
            if st in context:
                found.append(st.title())
        if found:
            return found

    # Credo format: "**Good For:** all skin types"
    m = re.search(r"good for:?\*?\*?\s*(.{0,200})", md_lower)
    if m:
        context = m.group(1)
        for st in skin_types:
            if st in context:
                found.append(st.title())
        if found:
            return found

    # Generic "skin type" context (but skip review filter sections)
    m = re.search(r"(?:ideal|best|recommended|suited)\s+for.*?(.{0,300})", md_lower)
    if m:
        context = m.group(1)
        for st in skin_types:
            if st in context:
                found.append(st.title())
        if found:
            return found

    # Broader fallback
    m = re.search(r"skin\s*type.*?[:\n](.{0,300})", md_lower, re.DOTALL)
    if m:
        context = m.group(1)
        for st in skin_types:
            if st in context:
                found.append(st.title())

    return found if found else None


EXTRACTORS = {
    "product_name": extract_product_name,
    "brand": extract_brand,
    "price": extract_price,
    "description": extract_description,
    "ingredients": extract_ingredients,
    "product_type": extract_product_type,
    "images": extract_images,
    "tags": extract_tags,
    "benefits": extract_benefits,
    "skin_types": extract_skin_types,
}


# ---------------------------------------------------------------------------
# FireCrawl API call
# ---------------------------------------------------------------------------
def get_firecrawl_app():
    if not FIRECRAWL_API_KEY or FIRECRAWL_API_KEY == "fc-YOUR_KEY_HERE":
        sys.exit(
            "ERROR: Set your FIRECRAWL_API_KEY in scrapers/pipeline/.env\n"
            "  Sign up at https://www.firecrawl.dev/pricing (500 free credits)"
        )
    return FirecrawlApp(api_key=FIRECRAWL_API_KEY)


def scrape_one_url(app, url, json_mode=False):
    """One FireCrawl API call. Returns dict or None on error."""
    try:
        if json_mode:
            doc = app.scrape(url, formats=["extract", "markdown"])
        else:
            doc = app.scrape(url, formats=["markdown"])
        # v4 returns a Document object — convert to dict
        if hasattr(doc, "model_dump"):
            return doc.model_dump()
        elif hasattr(doc, "__dict__"):
            return vars(doc)
        return doc
    except Exception as e:
        print(f"    ERROR: {e}")
        return None


def extract_fields(md, meta, json_mode=False, extracted_ai=None):
    """Run all 10 extractors. Returns (results_dict, found_count)."""
    results = {}
    found_count = 0
    for field in FIELDS:
        if json_mode and extracted_ai and field in extracted_ai and extracted_ai[field]:
            value = extracted_ai[field]
        else:
            value = EXTRACTORS[field](md, meta)
        results[field] = value
        if value:
            found_count += 1
    return results, found_count


# ---------------------------------------------------------------------------
# Single-product mode
# ---------------------------------------------------------------------------
def run_single(url, json_mode=False, output_path=None):
    """Scrape one URL and print field-by-field results."""
    app = get_firecrawl_app()

    print(f"\n{'='*60}")
    print(f"  FireCrawl Scraper — Credo Beauty Product")
    print(f"{'='*60}")
    print(f"  URL: {url}")
    print(f"  Mode: {'JSON (AI, ~5 credits)' if json_mode else 'Markdown (regex, 1 credit)'}")
    print(f"{'='*60}\n")

    result = scrape_one_url(app, url, json_mode=json_mode)
    if not result:
        print("  FAILED to scrape URL.")
        return None

    md = result.get("markdown", "") or ""
    meta = result.get("metadata", {}) or {}
    extracted_ai = result.get("extract", {}) or {}

    fields, found_count = extract_fields(md, meta, json_mode, extracted_ai)

    print(f"{'─'*60}")
    print(f"  FIELD-BY-FIELD EXTRACTION")
    print(f"{'─'*60}\n")

    for field in FIELDS:
        value = fields[field]
        label = field.replace("_", " ").title()
        if value:
            if isinstance(value, list):
                print(f"  [FOUND] {label}:")
                for item in value[:5]:
                    d = str(item) if len(str(item)) < 80 else str(item)[:77] + "..."
                    print(f"          - {d}")
                if len(value) > 5:
                    print(f"          ... +{len(value) - 5} more")
            else:
                d = str(value)
                if len(d) > 120:
                    d = d[:117] + "..."
                print(f"  [FOUND] {label}: {d}")
        else:
            print(f"  [MISSING] {label}")
        print()

    total = len(FIELDS)
    coverage = found_count / total * 100
    print(f"{'─'*60}")
    print(f"  SUMMARY: {found_count}/{total} fields — {coverage:.0f}% coverage")
    print(f"  Markdown: {len(md):,} chars | Metadata keys: {len(meta)}")
    print(f"{'─'*60}\n")

    if output_path:
        output = {
            "url": url,
            "fields": fields,
            "summary": {"found": found_count, "total": total, "coverage_pct": round(coverage, 1)},
            "raw_markdown_length": len(md),
            "metadata": meta,
        }
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"  Saved to: {output_path}")

    return fields


# ---------------------------------------------------------------------------
# Batch mode — scrape all products from Webflow CMS collections
# ---------------------------------------------------------------------------
def load_existing_results(output_file):
    """Load already-scraped slugs from an existing results file for resume."""
    if not output_file.exists():
        return {}
    try:
        with open(output_file) as f:
            data = json.load(f)
        return {p["slug"]: p for p in data.get("products", []) if p.get("slug")}
    except (json.JSONDecodeError, KeyError):
        return {}


def run_batch(collections, limit=0, dry_run=False, json_mode=False):
    """Pull products from Webflow CMS, then FireCrawl each Credo page."""

    if not WEBFLOW_API_TOKEN:
        sys.exit(
            "ERROR: Set WEBFLOW_API_TOKEN in scrapers/pipeline/.env\n"
            "  (Same token used by all other scrapers)"
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  FireCrawl Batch Scraper — Credo Beauty")
    print(f"{'='*60}")
    print(f"  Collections: {', '.join(collections)}")
    print(f"  Limit: {limit or 'all'} per collection")
    print(f"  Mode: {'DRY RUN (no credits used)' if dry_run else 'LIVE'}")
    if json_mode:
        print(f"  Extraction: AI JSON mode (~5 credits/product)")
    print(f"{'='*60}\n")

    # ── Phase 1: Discover products from Webflow CMS ──
    print("Phase 1: Fetching products from Webflow CMS...\n")
    catalog = {}
    total_products = 0

    for coll in collections:
        print(f"  [{coll}] Fetching...", end=" ", flush=True)
        products = get_products_for_collection(coll)
        if limit:
            products = products[:limit]
        catalog[coll] = products
        total_products += len(products)
        print(f"{len(products)} products with Credo URLs")

    credits_per = 5 if json_mode else 1
    credits_needed = total_products * credits_per
    print(f"\n  Total products: {total_products}")
    print(f"  Estimated credits: {credits_needed} ({credits_per}/product)")
    print()

    if dry_run:
        print(f"{'─'*60}")
        print(f"  DRY RUN — Product list (no FireCrawl calls)\n")
        for coll, products in catalog.items():
            print(f"  [{coll.upper()}] ({len(products)} products)")
            for p in products:
                print(f"    {p['brand'][:20]:20s}  {p['name'][:45]}")
            print()
        print(f"{'─'*60}")
        print(f"  To scrape, remove --dry-run")
        print(f"  Credits needed: {credits_needed}")
        return

    # ── Phase 2: FireCrawl each product ──
    app = get_firecrawl_app()
    grand_total = 0
    grand_found = 0
    credits_used = 0

    for coll in collections:
        products = catalog[coll]
        if not products:
            continue

        output_file = DATA_DIR / f"firecrawl_{coll}.json"
        existing = load_existing_results(output_file)
        skipped = 0

        print(f"\n{'━'*60}")
        print(f"  [{coll.upper()}] Scraping {len(products)} products...")
        print(f"  Output: {output_file}")
        if existing:
            print(f"  Resuming: {len(existing)} already scraped")
        print(f"{'━'*60}\n")

        results_list = list(existing.values())
        cat_found_total = 0
        cat_field_counts = {f: 0 for f in FIELDS}

        for i, prod in enumerate(products, 1):
            slug = prod["slug"]

            # Skip already-scraped (resume support)
            if slug in existing:
                skipped += 1
                continue

            url = prod["url"]
            print(f"  [{i}/{len(products)}] {prod['brand'][:15]:15s} | {prod['name'][:40]}...")

            result = scrape_one_url(app, url, json_mode=json_mode)
            credits_used += credits_per

            if not result:
                results_list.append({
                    "slug": slug,
                    "name": prod["name"],
                    "brand": prod["brand"],
                    "url": url,
                    "collection": coll,
                    "wf_id": prod["wf_id"],
                    "error": True,
                    "fields": {},
                    "coverage": 0,
                })
                print(f"           FAILED\n")
                time.sleep(1)
                continue

            md = result.get("markdown", "") or ""
            meta = result.get("metadata", {}) or {}
            extracted_ai = result.get("extract", {}) or {}

            fields, found_count = extract_fields(md, meta, json_mode, extracted_ai)

            # Use Webflow brand name as fallback if regex missed it
            if not fields.get("brand") and prod["brand"]:
                fields["brand"] = prod["brand"]
                found_count += 1

            coverage = found_count / len(FIELDS) * 100

            for f in FIELDS:
                if fields.get(f):
                    cat_field_counts[f] += 1
            cat_found_total += found_count
            grand_found += found_count
            grand_total += len(FIELDS)

            results_list.append({
                "slug": slug,
                "name": prod["name"],
                "brand": prod["brand"],
                "url": url,
                "collection": coll,
                "wf_id": prod["wf_id"],
                "error": False,
                "fields": fields,
                "coverage": round(coverage, 1),
            })

            print(f"           {found_count}/{len(FIELDS)} fields ({coverage:.0f}%)\n")

            # Save after each product (crash-safe / resume-safe)
            _save_results(output_file, coll, results_list, cat_field_counts)

            time.sleep(0.5)

        # ── Collection summary ──
        scraped_count = len(products) - skipped
        if scraped_count > 0:
            avg_coverage = cat_found_total / (scraped_count * len(FIELDS)) * 100
        else:
            avg_coverage = 0

        print(f"\n  [{coll.upper()}] Done — {scraped_count} scraped, {skipped} resumed")
        print(f"  Average coverage: {avg_coverage:.0f}%")
        print(f"  Field hit rates:")
        for f in FIELDS:
            n = scraped_count if scraped_count > 0 else 1
            pct = cat_field_counts[f] / n * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            print(f"    {f:20s} {bar} {cat_field_counts[f]:>3}/{scraped_count} ({pct:.0f}%)")

    # ── Grand summary ──
    print(f"\n{'='*60}")
    print(f"  BATCH COMPLETE")
    print(f"{'='*60}")
    print(f"  Products scraped:  {total_products}")
    print(f"  Credits used:      ~{credits_used}")
    if grand_total > 0:
        print(f"  Avg coverage:      {grand_found / grand_total * 100:.0f}%")
    print(f"  Results in:        {DATA_DIR}/")
    for coll in collections:
        f = DATA_DIR / f"firecrawl_{coll}.json"
        if f.exists():
            print(f"    {f.name}")
    print(f"{'='*60}\n")


def _save_results(output_file, collection, results_list, field_counts):
    """Save results incrementally (crash-safe)."""
    scraped = [r for r in results_list if not r.get("error")]
    output = {
        "collection": collection,
        "scraped_at": datetime.now().isoformat(),
        "total_products": len(results_list),
        "successful": len(scraped),
        "errors": len(results_list) - len(scraped),
        "field_coverage": {f: field_counts.get(f, 0) for f in FIELDS},
        "products": results_list,
    }
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="FireCrawl scraper for Credo Beauty products"
    )

    # Single-product args
    parser.add_argument("url", nargs="?", default=None,
                        help="Credo product URL to scrape")
    parser.add_argument("--demo", action="store_true",
                        help=f"Use demo URL: {DEMO_URL}")
    parser.add_argument("--json-mode", action="store_true",
                        help="AI-powered structured extraction (+4 credits/product)")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Save single-product results to JSON file")

    # Batch args
    parser.add_argument("--batch", action="store_true",
                        help="Batch mode: scrape all products from Webflow CMS collections")
    parser.add_argument("--collection", type=str, default=None,
                        help=f"Comma-separated collections: {','.join(ALL_COLLECTIONS)} (default: all)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max products per collection (0 = all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List products without scraping (no credits used)")

    args = parser.parse_args()

    # ── Batch mode ──
    if args.batch:
        if args.collection:
            colls = [c.strip().lower() for c in args.collection.split(",")]
            invalid = [c for c in colls if c not in WF_COLLECTIONS]
            if invalid:
                print(f"ERROR: Unknown collections: {invalid}")
                print(f"  Valid: {', '.join(ALL_COLLECTIONS)}")
                sys.exit(1)
        else:
            colls = ALL_COLLECTIONS

        run_batch(colls, limit=args.limit, dry_run=args.dry_run, json_mode=args.json_mode)
        return

    # ── Single-product mode ──
    if args.demo:
        url = DEMO_URL
    elif args.url:
        url = args.url
    else:
        parser.print_help()
        print(f"\nExamples:")
        print(f"  python firecrawl_scraper.py --demo")
        print(f"  python firecrawl_scraper.py --batch --dry-run")
        print(f"  python firecrawl_scraper.py --batch --collection makeups --limit 5")
        sys.exit(1)

    run_single(url, json_mode=args.json_mode, output_path=args.output)


if __name__ == "__main__":
    main()
