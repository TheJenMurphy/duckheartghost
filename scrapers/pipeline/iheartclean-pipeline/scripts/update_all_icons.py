#!/usr/bin/env python3
"""
Update all product icons using the new icon mapping system.
Re-processes detected_attributes and updates icon fields in Webflow.
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

from icon_mapping import map_attributes_to_icons, format_for_webflow

api_token = os.environ.get("WEBFLOW_API_TOKEN")
collection_id = os.environ.get("WEBFLOW_COLLECTION_ID")

headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json",
    "accept": "application/json",
}


def fetch_all_products():
    """Fetch all products from Webflow."""
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
        if len(batch) < 100:
            break

    return all_items


def extract_detected_attributes(field_data):
    """
    Extract detected attributes from existing icon fields.
    Since we store icon slugs in Webflow, we need to reverse-map them
    or use the description field which contains the original attributes.
    """
    # The 'description' field contains comma-separated detected attributes
    description = field_data.get("description", "")
    if description:
        attrs = [a.strip().lower().replace("-", "_") for a in description.split(",")]
        return [a for a in attrs if a]
    return []


def update_product_icons(item_id, icons):
    """Update a product's icon fields in Webflow."""
    field_data = {
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

    resp = requests.patch(
        f"https://api.webflow.com/v2/collections/{collection_id}/items/{item_id}",
        headers=headers,
        json={"fieldData": field_data}
    )
    resp.raise_for_status()
    return resp.json()


def main():
    print("=" * 60)
    print("UPDATE ALL PRODUCT ICONS")
    print("=" * 60)

    # Fetch all products
    print("\n1. Fetching all products from Webflow...")
    all_items = fetch_all_products()
    print(f"   Found {len(all_items)} total products")

    # Filter to active products only
    active_items = [i for i in all_items if not i.get("isArchived", False)]
    print(f"   Active products: {len(active_items)}")

    # Process each product
    print("\n2. Updating icons for each product...")

    success = 0
    failed = 0
    skipped = 0

    for i, item in enumerate(active_items, 1):
        item_id = item["id"]
        fd = item.get("fieldData", {})
        name = fd.get("name", "Unknown")[:40]

        # Get detected attributes from description field
        detected_attrs = extract_detected_attributes(fd)

        if not detected_attrs:
            print(f"   [{i}/{len(active_items)}] {name} - No attributes, skipping")
            skipped += 1
            continue

        # Map attributes to icons
        product = {"detected_attributes": detected_attrs}
        icons = map_attributes_to_icons(product)

        # Count how many icons we'll set
        total_icons = sum(len(v) for v in icons.values())

        try:
            update_product_icons(item_id, icons)
            print(f"   [{i}/{len(active_items)}] {name} - {total_icons} icons")
            success += 1
        except Exception as e:
            print(f"   [{i}/{len(active_items)}] {name} - ERROR: {e}")
            failed += 1

        # Rate limiting
        time.sleep(0.1)

    # Summary
    print(f"\n{'=' * 60}")
    print("COMPLETE")
    print("=" * 60)
    print(f"  Success: {success}")
    print(f"  Skipped (no attributes): {skipped}")
    print(f"  Failed: {failed}")


if __name__ == "__main__":
    main()
