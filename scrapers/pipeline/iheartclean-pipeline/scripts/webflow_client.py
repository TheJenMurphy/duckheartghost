#!/usr/bin/env python3
"""
Webflow CMS API Client for iHeartClean.beauty
Direct API integration - no Make.com needed.

Setup:
1. Get API token from Webflow Dashboard > Site Settings > Apps & Integrations
2. Get Collection ID from CMS panel URL or API
3. Set environment variables or pass directly
"""

import os
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

try:
    import requests
except ImportError:
    print("Install requests: pip install requests --break-system-packages")
    raise

# Webflow API v2 base URL
WEBFLOW_API_BASE = "https://api.webflow.com/v2"


@dataclass
class WebflowConfig:
    """Webflow API configuration"""
    api_token: str
    site_id: str
    collection_id: str
    
    @classmethod
    def from_env(cls):
        """Load config from environment variables"""
        return cls(
            api_token=os.environ.get("WEBFLOW_API_TOKEN", ""),
            site_id=os.environ.get("WEBFLOW_SITE_ID", ""),
            collection_id=os.environ.get("WEBFLOW_COLLECTION_ID", ""),
        )


class WebflowClient:
    """Webflow CMS API client"""

    # Brands collection ID
    BRANDS_COLLECTION_ID = "67d1b1e4b94243aa9c881b7a"

    def __init__(self, config: WebflowConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.api_token}",
            "Content-Type": "application/json",
            "accept": "application/json",
        })
        self._rate_limit_remaining = 60
        self._rate_limit_reset = 0
        self._brand_cache: Dict[str, str] = {}  # slug -> id mapping
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make API request with rate limiting"""
        # Check rate limit
        if self._rate_limit_remaining < 5:
            wait_time = max(0, self._rate_limit_reset - time.time()) + 1
            print(f"Rate limit low, waiting {wait_time:.0f}s...")
            time.sleep(wait_time)
        
        url = f"{WEBFLOW_API_BASE}{endpoint}"
        
        try:
            if method == "GET":
                resp = self.session.get(url)
            elif method == "POST":
                resp = self.session.post(url, json=data)
            elif method == "PATCH":
                resp = self.session.patch(url, json=data)
            elif method == "DELETE":
                resp = self.session.delete(url)
            else:
                raise ValueError(f"Unknown method: {method}")
            
            # Update rate limit info
            self._rate_limit_remaining = int(resp.headers.get("X-RateLimit-Remaining", 60))
            self._rate_limit_reset = float(resp.headers.get("X-RateLimit-Reset", 0))
            
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                print(f"Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                return self._request(method, endpoint, data)
            
            if not resp.ok:
                print(f"API Error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
            return resp.json() if resp.text else {}

        except requests.exceptions.HTTPError as e:
            print(f"API Error: {e}")
            response_text = ""
            if hasattr(e, 'response') and e.response is not None:
                response_text = e.response.text
                print(f"Response: {response_text}")
            # Re-raise with response body included for better error handling
            raise Exception(f"{e} | Response: {response_text}") from e
    
    # =========================================================================
    # COLLECTION OPERATIONS
    # =========================================================================
    
    def list_collections(self) -> List[Dict]:
        """List all collections for the site"""
        resp = self._request("GET", f"/sites/{self.config.site_id}/collections")
        return resp.get("collections", [])
    
    def get_collection_schema(self, collection_id: Optional[str] = None) -> Dict:
        """Get collection field schema"""
        cid = collection_id or self.config.collection_id
        return self._request("GET", f"/collections/{cid}")
    
    # =========================================================================
    # ITEM OPERATIONS
    # =========================================================================
    
    def list_items(self, collection_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """List ALL items in collection (handles pagination)"""
        cid = collection_id or self.config.collection_id
        all_items = []
        offset = 0

        while True:
            resp = self._request("GET", f"/collections/{cid}/items?limit={limit}&offset={offset}")
            items = resp.get("items", [])
            if not items:
                break
            all_items.extend(items)
            if len(items) < limit:
                break
            offset += limit

        return all_items
    
    def get_item(self, item_id: str, collection_id: Optional[str] = None) -> Dict:
        """Get single item by ID"""
        cid = collection_id or self.config.collection_id
        return self._request("GET", f"/collections/{cid}/items/{item_id}")
    
    def find_item_by_slug(self, slug: str, collection_id: Optional[str] = None) -> Optional[Dict]:
        """Find item by slug"""
        items = self.list_items(collection_id)
        for item in items:
            if item.get("fieldData", {}).get("slug") == slug:
                return item
        return None
    
    def _sanitize_field_data(self, field_data: Dict) -> Dict:
        """Remove fields with 'undefined', 'null', or invalid values before sending to Webflow."""
        invalid_values = {"undefined", "null", "None", "N/A", "n/a", ""}
        sanitized = {}
        skipped = []
        for key, value in field_data.items():
            # Skip fields with invalid string values
            if isinstance(value, str):
                if value.strip() in invalid_values:
                    skipped.append(f"{key}='{value}'")
                    continue
            # Skip image fields with invalid URLs
            if isinstance(value, dict) and "url" in value:
                url = value.get("url", "")
                if not url or str(url).strip() in invalid_values or not str(url).startswith("http"):
                    skipped.append(f"{key}=url:'{url}'")
                    continue
            sanitized[key] = value
        # Debug output removed - fields with invalid values are silently skipped
        return sanitized

    def create_item(self, field_data: Dict, collection_id: Optional[str] = None,
                    is_archived: bool = False, is_draft: bool = False) -> Dict:
        """Create new collection item"""
        cid = collection_id or self.config.collection_id

        # Sanitize field data to remove undefined/invalid values
        clean_data = self._sanitize_field_data(field_data)

        payload = {
            "isArchived": is_archived,
            "isDraft": is_draft,
            "fieldData": clean_data,
        }

        return self._request("POST", f"/collections/{cid}/items", payload)

    def update_item(self, item_id: str, field_data: Dict,
                    collection_id: Optional[str] = None) -> Dict:
        """Update existing item"""
        cid = collection_id or self.config.collection_id

        # Sanitize field data to remove undefined/invalid values
        clean_data = self._sanitize_field_data(field_data)

        payload = {"fieldData": clean_data}
        return self._request("PATCH", f"/collections/{cid}/items/{item_id}", payload)
    
    def upsert_item(self, field_data: Dict, collection_id: Optional[str] = None) -> Dict:
        """Create or update item based on slug. Handles stale slug index issues."""
        import random
        import string

        slug = field_data.get("slug")
        if not slug:
            raise ValueError("field_data must include 'slug'")

        existing = self.find_item_by_slug(slug, collection_id)

        if existing:
            print(f"Updating existing item: {slug}")
            return self.update_item(existing["id"], field_data, collection_id)
        else:
            print(f"Creating new item: {slug}")
            try:
                return self.create_item(field_data, collection_id)
            except Exception as e:
                # Handle stale slug index - append random suffix and retry
                if "already in database" in str(e) and "slug" in str(e):
                    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
                    new_slug = f"{slug}-{suffix}"
                    print(f"  Slug collision, retrying with: {new_slug}")
                    field_data["slug"] = new_slug
                    return self.create_item(field_data, collection_id)
                raise
    
    def delete_item(self, item_id: str, collection_id: Optional[str] = None) -> Dict:
        """Delete item"""
        cid = collection_id or self.config.collection_id
        return self._request("DELETE", f"/collections/{cid}/items/{item_id}")
    
    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================
    
    def batch_create(self, items: List[Dict], collection_id: Optional[str] = None) -> List[Dict]:
        """Create multiple items (handles rate limiting)"""
        results = []
        for i, item in enumerate(items):
            print(f"Creating item {i+1}/{len(items)}: {item.get('slug', 'unknown')}")
            try:
                result = self.create_item(item, collection_id)
                results.append({"success": True, "data": result})
            except Exception as e:
                results.append({"success": False, "error": str(e), "item": item})
            time.sleep(0.5)  # Rate limit buffer
        return results
    
    def batch_upsert(self, items: List[Dict], collection_id: Optional[str] = None) -> List[Dict]:
        """Upsert multiple items"""
        results = []
        for i, item in enumerate(items):
            print(f"Upserting {i+1}/{len(items)}: {item.get('slug', 'unknown')}")
            try:
                result = self.upsert_item(item, collection_id)
                results.append({"success": True, "data": result})
            except Exception as e:
                results.append({"success": False, "error": str(e), "item": item})
            time.sleep(0.5)
        return results
    
    # =========================================================================
    # PUBLISHING
    # =========================================================================
    
    def publish_items(self, item_ids: List[str], collection_id: Optional[str] = None) -> Dict:
        """Publish specific items"""
        cid = collection_id or self.config.collection_id
        payload = {"itemIds": item_ids}
        return self._request("POST", f"/collections/{cid}/items/publish", payload)
    
    def publish_site(self) -> Dict:
        """Publish entire site"""
        return self._request("POST", f"/sites/{self.config.site_id}/publish")

    # =========================================================================
    # BRAND OPERATIONS
    # =========================================================================

    def load_brand_cache(self) -> Dict[str, str]:
        """Load all brands into cache, returns slug -> id mapping"""
        if self._brand_cache:
            return self._brand_cache

        print("Loading brand cache...")
        brands = self.list_items(self.BRANDS_COLLECTION_ID)
        for brand in brands:
            slug = brand.get("fieldData", {}).get("slug", "")
            name = brand.get("fieldData", {}).get("name", "")
            if slug:
                self._brand_cache[slug] = brand["id"]
                # Also cache by normalized name for fuzzy matching
                normalized = name.lower().replace(" ", "-").replace("'", "")
                self._brand_cache[normalized] = brand["id"]
        print(f"  Cached {len(brands)} brands")
        return self._brand_cache

    def find_brand_id(self, brand_name: str) -> Optional[str]:
        """Find brand ID by name, returns None if not found"""
        import unicodedata

        if not self._brand_cache:
            self.load_brand_cache()

        # Normalize: remove accents, lowercase, replace spaces/underscores with hyphens
        def normalize(s):
            # Remove accents (é → e, etc.)
            normalized = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
            return normalized.lower().replace(" ", "-").replace("_", "-").replace("'", "")

        slug = normalize(brand_name)
        if slug in self._brand_cache:
            return self._brand_cache[slug]

        # Try partial matching
        for cached_slug, brand_id in self._brand_cache.items():
            if slug in cached_slug or cached_slug in slug:
                return brand_id

        return None

    def list_brands(self) -> List[Dict]:
        """List all brands"""
        return self.list_items(self.BRANDS_COLLECTION_ID)


# =============================================================================
# HELPER: Convert classified product to Webflow field data
# =============================================================================

def product_to_webflow_fields(product: Dict, brand_id: Optional[str] = None) -> Dict:
    """
    Convert classifier output to Webflow CMS field data.
    Matches the Clean Beauty Products collection schema.

    Args:
        product: Classified product dict from classifier
        brand_id: Optional Webflow brand item ID for the brand reference field
    """
    from icon_mapping import map_attributes_to_icons, format_for_webflow

    # Helper to ensure string values (AI sometimes returns lists)
    def ensure_string(val, max_len=256):
        if isinstance(val, list):
            val = val[0] if val else ""
        # Filter out invalid values like "undefined", "null", etc.
        invalid_values = {"undefined", "null", "None", "N/A", "n/a"}
        if val and str(val).strip() in invalid_values:
            return ""
        return str(val)[:max_len] if val else ""

    def is_valid_url(url):
        """Check if URL is valid (not undefined/null/empty)"""
        if not url:
            return False
        invalid_values = {"undefined", "null", "None", ""}
        return str(url).strip() not in invalid_values and str(url).startswith("http")

    detected = product.get("detected_attributes", [])

    # Map detected attributes to Webflow icon slugs
    icons = map_attributes_to_icons(product)

    # Build field data matching Webflow schema
    price = product.get("price") or 0
    if price == 0:
        price = 1  # Webflow requires a price, default to $1 if unknown

    # Add price tier to SPEND icons based on actual price
    # 4 tiers: budget, accessible, prestige, luxury
    # IMPORTANT: Only ONE price tier should show - remove any others first
    price_tiers = {"budget", "accessible", "prestige", "luxury"}

    # Remove any detected price tiers (we'll add the correct one based on actual price)
    icons["spend"] = [s for s in icons["spend"] if s not in price_tiers]

    # Calculate correct price tier from actual price
    if price < 20:
        price_tier = "budget"
    elif price < 50:
        price_tier = "accessible"
    elif price < 100:
        price_tier = "prestige"
    else:
        price_tier = "luxury"

    # Insert the single correct price tier at the beginning
    icons["spend"].insert(0, price_tier)

    # Add skin-types icon if AI detected skin types
    skin_types_field = product.get("skin_types", "")
    if skin_types_field and "skin-types" not in icons["suitability"]:
        icons["suitability"].insert(0, "skin-types")

    fields = {
        # Required fields
        "name": product.get("name", "Unknown Product")[:256],
        "slug": product.get("slug", "")[:256],
        "product-price": price,

        # Product info
        "brand-name-2": product.get("brand", ""),
        "description": ", ".join(detected[:10]) if detected else "",
        "product-url": product.get("credo_url", ""),  # Credo affiliate link only
        "affiliate-url": "",  # Left blank - user will input manually

        # 5 Dropdown fields (card back content) - sanitize to filter "undefined"
        "what-it-is-2": ensure_string(product.get("what_it_is", ""), 5000),
        "who-it-s-for-5": ensure_string(product.get("who_its_for", ""), 2000),
        "how-to-use-it-7": ensure_string(product.get("how_to_use", ""), 2000),
        "what-s-in-it": ensure_string(product.get("whats_in_it", ""), 5000),
        "what-it-s-in-3": ensure_string(product.get("whats_it_in", ""), 500),

        # Product classification fields (AI-generated) - ensure strings, not lists
        "product-type-3": ensure_string(product.get("product_type", "")),
        "category-3": ensure_string(product.get("category", "")),
        "formulation-3": ensure_string(product.get("formulation", "")),
        "packaging-2": ensure_string(product.get("packaging", "")),
        "finish-3": ensure_string(product.get("finish", "")),
        "coverage-4": ensure_string(product.get("coverage", "")),
        "skin-types": ensure_string(product.get("skin_types", "")),
        "instructions": ensure_string(product.get("instructions", ""), 2000),
        "packaging-inner-and-outer": ensure_string(product.get("packaging_inner_outer", ""), 500),

        # 9S Attributes - mapped to Webflow icon slugs for conditional visibility
        "stars-attributes-2": format_for_webflow(icons["stars"]),
        "source-attributes": format_for_webflow(icons["source"]),
        "safety-attributes": format_for_webflow(icons["safety"]),
        "support-attributes": format_for_webflow(icons["support"]),
        "suitability-attributes": format_for_webflow(icons["suitability"]),
        "structure-attributes-2": format_for_webflow(icons["structure"]),
        "substance-attributes": format_for_webflow(icons["substance"]),
        "sustainability-attributes": format_for_webflow(icons["sustainability"]),
        "spend-attributes-2": format_for_webflow(icons["spend"]),

        # Persona scores - use calculated scores from product, default to 0
        "family-score": product.get("family", product.get("family_score", 0)),
        "antiaging-score-2": product.get("antiaging", product.get("antiaging_score", 0)),
        "gentle-score": product.get("gentle", product.get("gentle_score", 0)),
        "inclusive-score": product.get("inclusive", product.get("inclusive_score", 0)),
        "genz-score": product.get("genz", product.get("genz_score", 0)),
        "skeptic-score": product.get("skeptic", product.get("skeptic_score", 0)),
    }

    # Add brand reference if provided (required field in Webflow)
    if brand_id:
        fields["brand"] = [brand_id]  # MultiReference field expects array of IDs

    # Add full ingredients list if available
    if product.get("ingredients"):
        fields["ingredients-2"] = product["ingredients"][:5000]

    # Add gallery images (gallery-image-1 through gallery-image-10)
    # Note: main-image field doesn't exist in Webflow schema - gallery-image-1 serves as main image
    images = product.get("images", [])
    main_img = product.get("main_image")

    # If main_image is valid and not already in images list, prepend it
    if is_valid_url(main_img) and main_img not in images:
        images = [main_img] + images

    for i, img_url in enumerate(images[:10], 1):
        if is_valid_url(img_url):
            fields[f"gallery-image-{i}"] = {"url": img_url}

    # Add video URL if available (VideoLink type expects a URL string)
    if is_valid_url(product.get("video_url")):
        fields["video"] = {"url": product["video_url"]}

    return fields


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Load from .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    config = WebflowConfig.from_env()
    
    if not config.api_token:
        print("Error: WEBFLOW_API_TOKEN not set")
        print("\nSet environment variables:")
        print("  export WEBFLOW_API_TOKEN=your_token")
        print("  export WEBFLOW_SITE_ID=your_site_id")
        print("  export WEBFLOW_COLLECTION_ID=your_collection_id")
        sys.exit(1)
    
    client = WebflowClient(config)
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "collections":
            collections = client.list_collections()
            for c in collections:
                print(f"  {c['id']}: {c['displayName']}")
        
        elif cmd == "schema":
            schema = client.get_collection_schema()
            print(json.dumps(schema, indent=2))
        
        elif cmd == "items":
            items = client.list_items()
            for item in items:
                print(f"  {item['id']}: {item.get('fieldData', {}).get('slug')}")
        
        else:
            print(f"Unknown command: {cmd}")
    else:
        print("Webflow Client CLI")
        print("Commands: collections, schema, items")
