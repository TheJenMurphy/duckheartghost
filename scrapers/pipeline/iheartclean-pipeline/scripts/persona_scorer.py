#!/usr/bin/env python3
"""
Persona Score Calculator for iHeartClean.beauty
Analyzes product data and calculates 6 persona scores (0-100).
"""

import os
import json
import re
import time
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

try:
    import requests
except ImportError:
    print("Install requests: pip install requests --break-system-packages")
    raise


# =============================================================================
# PERSONA SCORING RULES
# =============================================================================

# Keywords and attributes that influence each persona score
PERSONA_KEYWORDS = {
    "antiaging": {
        "high_value": [
            "anti-aging", "antiaging", "wrinkle", "fine lines", "collagen", "retinol",
            "retinoid", "peptide", "hyaluronic", "vitamin c", "niacinamide", "bakuchiol",
            "firming", "lifting", "plumping", "elasticity", "mature skin", "age-defying",
            "youth", "rejuvenating", "restorative", "dermatologist", "clinical",
            "proven results", "professional", "serum", "eye cream", "neck cream"
        ],
        "medium_value": [
            "hydrating", "moisturizing", "antioxidant", "brightening", "radiance",
            "glow", "smooth", "supple", "nourishing"
        ],
        "attributes": ["dermatologist_tested", "clinically_tested", "dermatologist_approved"]
    },
    "family": {
        "high_value": [
            "gentle", "safe", "non-toxic", "baby", "kids", "children", "family",
            "all ages", "multi-use", "everyday", "affordable", "budget", "value",
            "sensitive skin", "fragrance-free", "unscented", "hypoallergenic",
            "pediatrician", "ewg verified", "whole family", "body wash", "lotion"
        ],
        "medium_value": [
            "natural", "clean", "simple", "minimal", "basic", "essential",
            "mild", "soft", "soothing"
        ],
        "attributes": ["fragrance_free", "hypoallergenic", "ewg_verified", "safe_for_sensitive_skin"]
    },
    "gentle": {
        "high_value": [
            "sensitive", "gentle", "calming", "soothing", "fragrance-free", "unscented",
            "hypoallergenic", "non-irritating", "redness", "rosacea", "eczema",
            "dermatitis", "allergy-tested", "alcohol-free", "paraben-free", "minimal",
            "barrier", "microbiome", "ph-balanced", "ophthalmologist", "safe for eyes"
        ],
        "medium_value": [
            "mild", "soft", "delicate", "light", "non-comedogenic", "oil-free"
        ],
        "attributes": ["fragrance_free", "hypoallergenic", "paraben_free", "alcohol_free",
                       "safe_for_sensitive_skin", "dermatologist_tested"]
    },
    "inclusive": {
        "high_value": [
            "inclusive", "diverse", "all skin tones", "shade range", "bipoc",
            "black-owned", "latinx", "asian", "melanin", "deep skin", "dark skin",
            "universal", "adaptive", "accessible", "representation", "woman-owned",
            "lgbtq", "queer", "community", "underrepresented"
        ],
        "medium_value": [
            "for all", "everyone", "every skin", "any skin", "buildable"
        ],
        "attributes": ["bipoc_owned", "woman_owned", "inclusive_shades"]
    },
    "genz": {
        "high_value": [
            "sustainable", "eco", "recyclable", "refillable", "biodegradable",
            "carbon neutral", "ocean", "reef safe", "trending", "viral", "tiktok",
            "aesthetic", "minimalist", "clean girl", "glazed", "glass skin",
            "dopamine", "y2k", "cottagecore", "indie", "vegan", "cruelty-free"
        ],
        "medium_value": [
            "natural", "organic", "green", "plant-based", "botanical",
            "fresh", "glow", "dewy", "effortless"
        ],
        "attributes": ["vegan", "cruelty_free", "recyclable_packaging", "sustainable",
                       "reef_safe", "carbon_neutral"]
    },
    "skeptic": {
        "high_value": [
            "clinically proven", "third-party", "tested", "certified", "ewg",
            "verified", "transparent", "ingredient list", "science-backed",
            "peer-reviewed", "dermatologist", "studies", "research", "lab",
            "efficacy", "results", "before after", "no fillers", "simple ingredients"
        ],
        "medium_value": [
            "honest", "authentic", "real", "evidence", "quality", "pure"
        ],
        "attributes": ["ewg_verified", "clinically_tested", "dermatologist_tested",
                       "third_party_tested", "certified_organic"]
    }
}


def calculate_keyword_score(text: str, keywords: Dict) -> int:
    """Calculate score based on keyword matching."""
    if not text:
        return 0  # No data = no score

    text_lower = text.lower()
    score = 0  # Start from 0

    # High value keywords: +15 each (max 60 points)
    high_matches = sum(1 for kw in keywords.get("high_value", []) if kw in text_lower)
    score += min(high_matches * 15, 60)

    # Medium value keywords: +8 each (max 30 points)
    medium_matches = sum(1 for kw in keywords.get("medium_value", []) if kw in text_lower)
    score += min(medium_matches * 8, 30)

    return min(score, 100)


def calculate_attribute_score(attributes: List[str], persona_attrs: List[str]) -> int:
    """Calculate bonus score from 9S attributes."""
    if not attributes:
        return 0

    matches = sum(1 for attr in persona_attrs if attr in attributes)
    return min(matches * 10, 30)  # Max 30 bonus points


def calculate_persona_scores(product: Dict) -> Dict[str, int]:
    """
    Calculate all 6 persona scores for a product.
    Returns dict with scores 0-100 for each persona.
    """
    # Gather product text for analysis
    name = product.get("name", "") or ""
    brand = product.get("brand-name-2", "") or ""
    description = product.get("what-it-is-2", "") or ""
    who_for = product.get("who-it-s-for-5", "") or ""
    ingredients = product.get("ingredients-2", "") or ""
    how_to_use = product.get("how-to-use-it-7", "") or ""
    whats_in_it = product.get("what-s-in-it", "") or ""

    # Combine all text
    full_text = f"{name} {brand} {description} {who_for} {ingredients} {how_to_use} {whats_in_it}"

    # Extract 9S attributes
    detected_attrs = []
    attr_fields = [
        "stars-attributes-2", "source-attributes", "safety-attributes",
        "support-attributes", "suitability-attributes", "structure-attributes-2",
        "substance-attributes", "sustainability-attributes", "spend-attributes-2"
    ]
    for field in attr_fields:
        val = product.get(field, "")
        if val:
            detected_attrs.extend(val.lower().replace("-", "_").split(","))
    detected_attrs = [a.strip() for a in detected_attrs if a.strip()]

    scores = {}
    for persona, keywords in PERSONA_KEYWORDS.items():
        # Base keyword score
        keyword_score = calculate_keyword_score(full_text, keywords)

        # Attribute bonus
        attr_bonus = calculate_attribute_score(detected_attrs, keywords.get("attributes", []))

        # Final score (capped at 100)
        scores[persona] = min(keyword_score + attr_bonus, 100)

    return scores


# =============================================================================
# WEBFLOW API
# =============================================================================

class WebflowScorer:
    """Update Webflow products with persona scores."""

    def __init__(self):
        self.api_token = os.environ.get("WEBFLOW_API_TOKEN", "")
        self.collection_id = os.environ.get("WEBFLOW_COLLECTION_ID", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "accept": "application/json",
        })
        self._rate_limit_remaining = 60

    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make API request with rate limiting."""
        if self._rate_limit_remaining < 5:
            print("Rate limit low, waiting...")
            time.sleep(2)

        url = f"https://api.webflow.com/v2{endpoint}"

        if method == "GET":
            resp = self.session.get(url)
        elif method == "PATCH":
            resp = self.session.patch(url, json=data)
        else:
            raise ValueError(f"Unknown method: {method}")

        self._rate_limit_remaining = int(resp.headers.get("X-RateLimit-Remaining", 60))

        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 60))
            print(f"Rate limited. Waiting {wait}s...")
            time.sleep(wait)
            return self._request(method, endpoint, data)

        if not resp.ok:
            print(f"API Error: {resp.status_code} - {resp.text[:200]}")

        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def get_all_products(self) -> List[Dict]:
        """Get all products from Webflow CMS."""
        items = []
        offset = 0
        limit = 100

        while True:
            print(f"  Fetching products (offset {offset})...")
            resp = self._request("GET", f"/collections/{self.collection_id}/items?offset={offset}&limit={limit}")
            batch = resp.get("items", [])
            if not batch:
                break
            items.extend(batch)
            offset += limit
            if len(batch) < limit:
                break

        return items

    def update_product_scores(self, item_id: str, scores: Dict[str, int]) -> bool:
        """Update a product's persona scores."""
        field_data = {
            "antiaging-score-2": scores["antiaging"],
            "family-score": scores["family"],
            "gentle-score": scores["gentle"],
            "inclusive-score": scores["inclusive"],
            "genz-score": scores["genz"],
            "skeptic-score": scores["skeptic"],
        }

        try:
            self._request("PATCH", f"/collections/{self.collection_id}/items/{item_id}", {"fieldData": field_data})
            return True
        except Exception as e:
            print(f"    Error updating: {e}")
            return False


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main function to score all products."""
    print("=" * 60)
    print("PERSONA SCORE CALCULATOR")
    print("=" * 60)

    scorer = WebflowScorer()

    if not scorer.api_token:
        print("Error: WEBFLOW_API_TOKEN not set")
        return

    # Get all products
    print("\n1. Fetching products from Webflow...")
    products = scorer.get_all_products()
    print(f"   Found {len(products)} products")

    # Calculate and update scores
    print("\n2. Calculating and updating persona scores...")
    success = 0
    failed = 0

    for i, product in enumerate(products, 1):
        item_id = product.get("id")
        field_data = product.get("fieldData", {})
        name = field_data.get("name", "Unknown")

        print(f"\n   [{i}/{len(products)}] {name[:50]}...")

        # Calculate scores
        scores = calculate_persona_scores(field_data)
        print(f"      Antiaging: {scores['antiaging']}, Family: {scores['family']}, Gentle: {scores['gentle']}")
        print(f"      Inclusive: {scores['inclusive']}, GenZ: {scores['genz']}, Skeptic: {scores['skeptic']}")

        # Update in Webflow
        if scorer.update_product_scores(item_id, scores):
            print(f"      Updated!")
            success += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"  Updated: {success}")
    print(f"  Failed: {failed}")


if __name__ == "__main__":
    main()
