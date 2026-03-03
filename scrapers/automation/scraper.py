"""
Web scraping module for iHeartClean Product Automation
Fetches product data from Credo Beauty and brand Shopify stores.
"""
import re
import requests
from difflib import SequenceMatcher
from typing import List, Optional
from urllib.parse import urlparse

from config import IMAGE_FILTER_KEYWORDS

# ---------------------------------------------------------------------------
# Set / Kit / Bundle detection
# ---------------------------------------------------------------------------

_SET_KEYWORDS = re.compile(
    r'\b(set|kit|bundle|trio|duo|collection|quartet)\b',
    re.IGNORECASE,
)


def is_set_product(product_data: dict) -> bool:
    """Return True if the product looks like a set/kit/bundle.

    Checks both ``product_type`` and ``title`` for keywords such as
    "Set", "Kit", "Bundle", "Trio", "Duo", "Collection", "Quartet"
    (case-insensitive).
    """
    for field in ("product_type", "title"):
        value = product_data.get(field) or ""
        if _SET_KEYWORDS.search(value):
            return True
    return False


def extract_component_handles(body_html: str, brand_domain: str = "") -> List[str]:
    """Parse component product handles from the description HTML.

    Looks for ``<a href="...">`` tags that point to ``/products/{handle}``
    paths — either as relative links or links matching *brand_domain*.

    Returns a deduplicated list of handles in the order they first appear.
    """
    if not body_html:
        return []

    # Normalise the brand domain for comparison (strip scheme + www.)
    domain_compare = ""
    if brand_domain:
        parsed = urlparse(
            brand_domain if brand_domain.startswith("http") else f"https://{brand_domain}"
        )
        domain_compare = parsed.netloc.lower().removeprefix("www.")

    # Find all href values inside <a> tags
    href_pattern = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\']', re.IGNORECASE)

    seen: set = set()
    handles: List[str] = []

    for href in href_pattern.findall(body_html):
        parsed_href = urlparse(href)
        path = parsed_href.path.rstrip("/")

        # Must be a /products/<handle> path
        segments = path.split("/")
        try:
            idx = segments.index("products")
        except ValueError:
            continue

        if idx + 1 >= len(segments):
            continue

        handle = segments[idx + 1]
        if not handle:
            continue

        # If it has a host, it must match the brand domain
        href_host = parsed_href.netloc.lower().removeprefix("www.")
        if href_host and domain_compare and href_host != domain_compare:
            continue

        if handle not in seen:
            seen.add(handle)
            handles.append(handle)

    return handles


# Boilerplate anchor/bold text to ignore when title-matching
_BOILERPLATE = {
    "shop now", "learn more", "read more", "buy now", "add to cart",
    "view all", "see details", "click here", "details", "shop",
    "free shipping", "subscribe", "sale", "new", "best seller",
}


def extract_component_handles_by_title(
    body_html: str,
    catalog: List[dict],
    self_handle: str = "",
) -> List[str]:
    """Fallback: match component names in HTML against catalog titles.

    Extracts text from <a> tags and <strong>/<b>/<em>/<i> tags in the
    body_html, then fuzzy-matches against product titles in the catalog.
    Returns handles for matches above a similarity threshold.
    """
    if not body_html or not catalog:
        return []

    # Extract candidate text from relevant tags
    tag_pattern = re.compile(
        r'<(?:a|strong|b|em|i)\b[^>]*>(.*?)</(?:a|strong|b|em|i)>',
        re.IGNORECASE | re.DOTALL,
    )
    raw_candidates = tag_pattern.findall(body_html)

    # Strip nested HTML and normalize whitespace
    candidates = []
    for raw in raw_candidates:
        text = re.sub(r'<[^>]+>', '', raw).strip()
        text = re.sub(r'\s+', ' ', text)
        if 4 <= len(text) <= 80 and text.lower() not in _BOILERPLATE:
            candidates.append(text)

    if not candidates:
        return []

    seen: set = set()
    handles: List[str] = []

    for candidate in candidates:
        candidate_lower = candidate.lower()
        for product in catalog:
            title = product.get("title", "")
            handle = product.get("handle", "")
            if not title or not handle:
                continue
            if handle == self_handle or handle in seen:
                continue
            ratio = SequenceMatcher(None, candidate_lower, title.lower()).ratio()
            if ratio >= 0.75:
                seen.add(handle)
                handles.append(handle)
                break  # one match per candidate

    return handles


def extract_product_slug(url: str) -> str:
    """Extract the product slug from a URL (last path segment)."""
    url = url.rstrip("/")
    slug = url.split("/")[-1]
    slug = slug.split("?")[0]
    return slug


def fetch_json(url: str, timeout: int = 30) -> Optional[dict]:
    """Fetch JSON from a URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def fetch_html(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch HTML from a URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html"
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching HTML from {url}: {e}")
        return None


def extract_ingredients_from_html(html: str) -> Optional[str]:
    """
    Extract full ingredient list from Credo Beauty product page HTML.
    The ingredients are in a tab section with id="ingredients".
    """
    if not html:
        return None

    # Pattern to find the ingredients tab content
    # Looking for: <div id="ingredients"...>...<div class="...ingredients-p">INGREDIENTS</div>
    patterns = [
        # Primary pattern: ingredients-p class
        r'class="[^"]*ingredients-p[^"]*"[^>]*>\s*([^<]+(?:<[^>]+>[^<]*)*?)\s*</div>',
        # Backup: id="ingredients" section with detailscontent-p
        r'id="ingredients"[^>]*>.*?class="[^"]*detailscontent-p[^"]*"[^>]*>\s*([^<]+)\s*</div>',
        # Fallback: Full ingredient list header followed by content
        r'Full ingredient[s]?\s*list[^<]*</[^>]+>\s*</div>\s*<div[^>]*>\s*([A-Za-z][^<]{50,}?)\s*</div>',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            ingredients = match.group(1).strip()
            # Clean up HTML tags
            ingredients = re.sub(r'<[^>]+>', '', ingredients)
            # Decode common HTML entities
            html_entities = {
                '&#39;': "'",
                '&quot;': '"',
                '&amp;': '&',
                '&lt;': '<',
                '&gt;': '>',
                '&nbsp;': ' ',
                '&#x27;': "'",
            }
            for entity, char in html_entities.items():
                ingredients = ingredients.replace(entity, char)
            # Normalize whitespace
            ingredients = re.sub(r'\s+', ' ', ingredients)
            ingredients = ingredients.strip()
            if len(ingredients) > 20:  # Sanity check - should be substantial
                return ingredients

    return None


def fetch_credo_product(credo_url: str) -> Optional[dict]:
    """
    Fetch product data from Credo Beauty.
    Appends .json to the URL to get JSON data.
    """
    json_url = credo_url.rstrip("/") + ".json"
    return fetch_json(json_url)


def fetch_brand_product(brand_domain: str, product_slug: str) -> Optional[dict]:
    """
    Fetch product data from brand's Shopify store.

    If brand_domain is a full URL ending in .json, use it directly.
    Otherwise, constructs URL: https://www.{brand_domain}/products/{slug}.json
    """
    domain = brand_domain.strip()

    # If it's already a full JSON URL, use it directly
    if domain.endswith(".json"):
        json_url = domain
    else:
        # Ensure domain has proper format
        if not domain.startswith("http"):
            domain = f"https://www.{domain}"
        if domain.startswith("https://www.www."):
            domain = domain.replace("https://www.www.", "https://www.")
        json_url = f"{domain}/products/{product_slug}.json"

    return fetch_json(json_url)


def extract_product_data(brand_json: dict) -> dict:
    """
    Extract relevant product data from Shopify JSON response.
    """
    product = brand_json.get("product", {})

    # Get first variant price
    variants = product.get("variants", [])
    price = variants[0].get("price") if variants else None

    # Get main image
    main_image = product.get("image", {})
    main_image_src = main_image.get("src") if main_image else None

    # Get all images
    images = product.get("images", [])

    # Filter images - exclude those with filtered keywords in alt text
    filtered_images = []
    for img in images:
        alt_text = (img.get("alt") or "").lower()
        should_exclude = any(keyword in alt_text for keyword in IMAGE_FILTER_KEYWORDS)
        if not should_exclude:
            filtered_images.append(img)

    # Get image URLs
    gallery_image_urls = [img.get("src") for img in filtered_images if img.get("src")]

    return {
        "title": product.get("title"),
        "vendor": product.get("vendor"),
        "price": price,
        "description": product.get("body_html"),
        "product_type": product.get("product_type"),
        "tags": product.get("tags", []),
        "main_image": main_image_src,
        "gallery_images": gallery_image_urls,
        "handle": product.get("handle")
    }


def build_merged_data(product_data: dict) -> str:
    """
    Build the merged data string for AI categorization.
    """
    tags_str = ", ".join(product_data.get("tags", [])) if isinstance(product_data.get("tags"), list) else product_data.get("tags", "")

    merged = f"""PRODUCT TITLE: {product_data.get('title', 'N/A')}
BRAND: {product_data.get('vendor', 'N/A')}
PRICE: ${product_data.get('price', 'N/A')}
DESCRIPTION: {product_data.get('description', 'N/A')}
PRODUCT TYPE: {product_data.get('product_type', 'N/A')}
TAGS (certifications and attributes): {tags_str}
MAIN IMAGE: {product_data.get('main_image', 'N/A')}"""

    return merged


def scrape_product(credo_url: str, brand_domain: str) -> Optional[dict]:
    """
    Main scraping function - fetches from both Credo and brand site.
    Returns combined product data.
    """
    print(f"Scraping product from Credo: {credo_url}")

    # Extract product slug from Credo URL
    product_slug = extract_product_slug(credo_url)
    print(f"Product slug: {product_slug}")

    # Fetch from Credo (optional - for additional data)
    credo_data = fetch_credo_product(credo_url)
    if credo_data:
        print("Successfully fetched Credo data")

    # Fetch HTML from Credo to get full ingredient list
    print("Fetching Credo HTML for ingredients...")
    credo_html = fetch_html(credo_url)
    ingredients = None
    if credo_html:
        ingredients = extract_ingredients_from_html(credo_html)
        if ingredients:
            print(f"  ✓ Extracted full ingredient list ({len(ingredients)} chars)")
        else:
            print("  ✗ Could not extract ingredients from HTML")
    else:
        print("  ✗ Failed to fetch Credo HTML")

    # Fetch from brand's Shopify store
    print(f"Fetching from brand domain: {brand_domain}")
    brand_json = fetch_brand_product(brand_domain, product_slug)

    if not brand_json:
        print("Failed to fetch brand product data")
        return None

    print("Successfully fetched brand product data")

    # Extract and return product data
    product_data = extract_product_data(brand_json)
    product_data["credo_url"] = credo_url
    product_data["ingredients"] = ingredients  # Add full ingredient list
    product_data["merged_data"] = build_merged_data(product_data)

    return product_data


if __name__ == "__main__":
    # Test the module
    test_credo_url = "https://credobeauty.com/products/test-product"
    test_brand_domain = "osea.com"

    print("Testing scraper module...")
    print(f"Slug extraction: {extract_product_slug(test_credo_url)}")
