#!/usr/bin/env python3
"""
Add format icons (tube, jar, bottle, etc.) to structure-attributes-2 field.
Infers format from product name, type, and description.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

api_token = os.environ.get("WEBFLOW_API_TOKEN")
collection_id = os.environ.get("WEBFLOW_COLLECTION_ID")

headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json",
    "accept": "application/json",
}


def infer_format(text, product_type):
    """Infer packaging format from product text."""
    text = text.lower()
    ptype = (product_type or "").lower()

    # Order matters - more specific matches first
    rules = [
        ("dropper", ["dropper", "pipette", "serum bottle"]),
        ("pump", ["pump bottle", "pump dispenser", " pump", "airless pump"]),
        ("cushion", ["cushion", "cushion compact"]),
        ("roll-on", ["roll-on", "rollerball", "roll on"]),
        ("palette", ["palette", " quad ", "eyeshadow palette", "lip palette"]),
        ("compact", ["compact", "pressed powder compact", "mirror compact"]),
        ("pencil", ["pencil", "eyeliner pencil", "brow pencil", "lip pencil", "liner pencil"]),
        ("pen", [" pen ", "felt tip pen", "marker pen", "click pen"]),
        ("wand", ["wand", "mascara wand"]),
        ("stick", ["stick", "lipstick", "balm stick", "deodorant stick", "highlighter stick"]),
        ("spray", ["spray bottle", "mist bottle", "spritz", "spray can"]),
        ("tube", ["tube", "squeeze tube", "metal tube"]),
        ("jar", ["jar", " pot ", " tub ", "glass jar"]),
        ("bottle", ["bottle", "glass bottle", "plastic bottle"]),
    ]

    for fmt, keywords in rules:
        for kw in keywords:
            if kw in text:
                return fmt

    # Infer from product type
    type_rules = {
        "mascara": "wand",
        "lipstick": "stick",
        "lip gloss": "wand",
        "eyeliner": "pencil",
        "serum": "dropper",
        "foundation": "pump",
        "concealer": "tube",
        "moisturizer": "jar",
        "cream": "jar",
        "cleanser": "pump",
        "toner": "bottle",
        "mist": "spray",
        "setting spray": "spray",
        "primer": "pump",
        "sunscreen": "tube",
        "lip balm": "stick",
        "eye cream": "tube",
        "face oil": "dropper",
        "body lotion": "pump",
        "shampoo": "bottle",
        "conditioner": "bottle",
        "blush": "compact",
        "bronzer": "compact",
        "highlighter": "compact",
        "eyeshadow": "palette",
        "powder": "compact",
        "setting powder": "compact",
    }

    for key, fmt in type_rules.items():
        if key in ptype:
            return fmt

    return None


def main():
    print("=" * 60)
    print("ADD FORMAT ICONS TO STRUCTURE ATTRIBUTES")
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
        if len(batch) < 100:
            break

    print(f"   Total: {len(all_items)} products")

    # Process each product
    print("\n2. Processing products...")
    updated = 0
    failed = 0
    skipped = 0

    # Format icons we're looking for
    format_icons = {"tube", "jar", "bottle", "pump", "stick", "compact", "dropper",
                    "spray", "pencil", "pen", "palette", "roll-on", "wand", "cushion"}

    for i, item in enumerate(all_items, 1):
        fd = item.get("fieldData", {})
        item_id = item["id"]
        name = fd.get("name", "")
        product_type = fd.get("product-type-3", "")
        description = fd.get("description", "") or ""
        what_it_is = fd.get("what-it-is-2", "") or ""

        current_structure = fd.get("structure-attributes-2") or ""

        # Check if already has a format icon
        current_icons = set(s.strip().lower() for s in current_structure.split(",") if s.strip())
        has_format = bool(current_icons & format_icons)

        if has_format:
            skipped += 1
            continue

        # Build text for inference
        full_text = f"{name} {product_type} {description} {what_it_is}"

        # Infer format
        inferred_format = infer_format(full_text, product_type)

        if not inferred_format:
            skipped += 1
            continue

        # Build new structure attributes - add format to existing
        if current_structure:
            new_structure = f"{current_structure}, {inferred_format}"
        else:
            new_structure = inferred_format

        # Update in Webflow
        try:
            resp = requests.patch(
                f"https://api.webflow.com/v2/collections/{collection_id}/items/{item_id}",
                headers=headers,
                json={"fieldData": {"structure-attributes-2": new_structure}}
            )
            resp.raise_for_status()
            updated += 1

            if i % 100 == 0:
                print(f"   [{i}/{len(all_items)}] Updated: {updated}")

        except Exception as e:
            print(f"   FAILED: {name[:30]} - {e}")
            failed += 1

        time.sleep(0.15)

    print(f"\n{'=' * 60}")
    print("COMPLETE")
    print("=" * 60)
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")


if __name__ == "__main__":
    main()
