#!/usr/bin/env python3
"""
Update all products with new icon mappings.
Re-processes detected attributes and updates 9S fields in Webflow.
"""

import os
import time
import requests
from dotenv import load_dotenv
from icon_mapping import map_attributes_to_icons, format_for_webflow

load_dotenv()

api_token = os.environ.get("WEBFLOW_API_TOKEN")
collection_id = os.environ.get("WEBFLOW_COLLECTION_ID")

headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json",
    "accept": "application/json",
}

PRICE_TIERS = {"budget", "accessible", "prestige", "luxury"}


def get_price_tier(price):
    """Get the correct price tier based on actual price."""
    if price < 20:
        return "budget"
    elif price < 50:
        return "accessible"
    elif price < 100:
        return "prestige"
    else:
        return "luxury"


def extract_attributes_from_product(field_data):
    """Extract detected attributes from product field data."""
    # The 'description' field contains comma-separated detected attributes
    desc = field_data.get("description", "")
    if not desc:
        return []

    attrs = [a.strip() for a in desc.split(",") if a.strip()]
    return attrs


def main():
    print("=" * 60)
    print("UPDATE PRODUCTS WITH NEW ICON MAPPINGS")
    print("=" * 60)

    # Get all products
    print("\n1. Fetching all products...")
    all_items = []
    offset = 0
    while True:
        resp = requests.get(
            f"https://api.webflow.com/v2/collections/{collection_id}/items?limit=100&offset={offset}",
            headers=headers
        )
        batch = resp.json().get("items", [])
        if not batch:
            break
        all_items.extend(batch)
        offset += 100
        print(f"   Fetched {len(all_items)} products...")
        if len(batch) < 100:
            break

    print(f"   Total: {len(all_items)} products")

    # Process each product
    print("\n2. Updating icon mappings...")
    success = 0
    failed = 0
    skipped = 0

    for i, item in enumerate(all_items, 1):
        fd = item.get("fieldData", {})
        item_id = item["id"]
        name = fd.get("name", "Unknown")[:40]
        price = fd.get("product-price", 0) or 0

        # Extract detected attributes
        attrs = extract_attributes_from_product(fd)

        if not attrs:
            skipped += 1
            continue

        # Create a mock product dict for icon mapping
        product = {"detected_attributes": attrs}
        icons = map_attributes_to_icons(product)

        # Fix spend icons - ensure only one price tier
        icons["spend"] = [s for s in icons["spend"] if s not in PRICE_TIERS]
        icons["spend"].insert(0, get_price_tier(price))

        # Build update payload
        update_data = {
            "stars-attributes-2": format_for_webflow(icons["stars"]),
            "source-attributes": format_for_webflow(icons["source"]),
            "safety-attributes": format_for_webflow(icons["safety"]),
            "support-attributes": format_for_webflow(icons["support"]),
            "suitability-attributes": format_for_webflow(icons["suitability"]),
            "structure-attributes-2": format_for_webflow(icons["structure"]),
            "substance-attributes": format_for_webflow(icons["substance"]),
            "sustainability-attributes": format_for_webflow(icons["sustainability"]),
            "spend-attributes-2": format_for_webflow(icons["spend"]),
        }

        try:
            resp = requests.patch(
                f"https://api.webflow.com/v2/collections/{collection_id}/items/{item_id}",
                headers=headers,
                json={"fieldData": update_data}
            )
            resp.raise_for_status()
            success += 1

            if i % 50 == 0 or i == len(all_items):
                print(f"   [{i}/{len(all_items)}] Updated {success} products...")

        except Exception as e:
            print(f"   [{i}/{len(all_items)}] FAILED: {name} - {e}")
            failed += 1

        time.sleep(0.25)  # Rate limiting

    print(f"\n{'=' * 60}")
    print("COMPLETE")
    print("=" * 60)
    print(f"  Updated: {success}")
    print(f"  Failed: {failed}")
    print(f"  Skipped (no attributes): {skipped}")


if __name__ == "__main__":
    main()
