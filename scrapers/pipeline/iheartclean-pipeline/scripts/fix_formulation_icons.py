#!/usr/bin/env python3
"""
Add formulation icons (liquid, cream, gel, etc.) to structure-attributes-2 field.
Uses the formulation-3 text field and infers from product name/description.
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

# Valid formulation icons for structure category
FORMULATION_ICONS = {
    "liquid", "cream", "powder", "gel", "oil", "serum", "balm",
    "lotion", "mousse", "butter", "milk", "foam", "wax", "mist"
}


def normalize_formulation_to_icon(val):
    """Convert formulation-3 text value to icon name."""
    if not val:
        return None

    val_lower = val.lower().strip()

    # Direct mappings
    mappings = {
        "cream": "cream",
        "creme": "cream",
        "liquid": "liquid",
        "serum": "serum",
        "powder": "powder",
        "gel": "gel",
        "oil": "oil",
        "balm": "balm",
        "mousse": "mousse",
        "foam": "foam",
        "lotion": "lotion",
        "mist": "mist",
        "butter": "butter",
        "milk": "milk",
        "wax": "wax",
        "solid": "balm",  # Map solid to balm
        "emulsion": "cream",  # Map emulsion to cream
        "essence": "serum",  # Map essence to serum
        "clay": "cream",  # Map clay to cream
    }

    for key, icon in mappings.items():
        if key in val_lower:
            return icon

    return None


def infer_formulation(text, product_type):
    """Infer formulation from product text and type."""
    text = text.lower()
    ptype = (product_type or "").lower()

    rules = [
        ("cream", ["cream", "crème", "creme", "moisturizer", "night cream", "day cream"]),
        ("serum", ["serum", "concentrate", "ampoule", "essence"]),
        ("gel", ["gel ", " gel", "gel-cream", "jelly"]),
        ("powder", ["powder", "pressed powder", "loose powder", "setting powder"]),
        ("oil", [" oil ", "facial oil", "body oil", "cleansing oil", "oil-"]),
        ("balm", ["balm", "salve", "lip balm", "solid", "stick"]),
        ("liquid", ["liquid", "fluid"]),
        ("mousse", ["mousse", "whip"]),
        ("foam", ["foam", "foaming"]),
        ("lotion", ["lotion"]),
        ("mist", ["mist", "toner mist", "facial mist", "spray"]),
        ("butter", ["butter", "body butter"]),
        ("milk", ["milk", "cleansing milk"]),
        ("wax", ["wax", "pomade"]),
    ]

    for form, keywords in rules:
        for kw in keywords:
            if kw in text:
                return form

    # Infer from product type
    type_rules = {
        "serum": "serum",
        "cream": "cream",
        "moisturizer": "cream",
        "cleanser": "gel",
        "oil": "oil",
        "mask": "cream",
        "mist": "mist",
        "toner": "liquid",
        "foundation": "liquid",
        "concealer": "liquid",
        "lipstick": "balm",
        "lip gloss": "liquid",
        "mascara": "liquid",
        "eyeshadow": "powder",
        "blush": "powder",
        "bronzer": "powder",
        "highlighter": "powder",
        "setting spray": "mist",
        "primer": "liquid",
        "body wash": "gel",
        "shampoo": "liquid",
        "conditioner": "cream",
    }

    for key, form in type_rules.items():
        if key in ptype:
            return form

    return None


def main():
    print("=" * 60)
    print("ADD FORMULATION ICONS TO STRUCTURE ATTRIBUTES")
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

    for i, item in enumerate(all_items, 1):
        fd = item.get("fieldData", {})
        item_id = item["id"]
        name = fd.get("name", "")
        product_type = fd.get("product-type-3", "")
        description = fd.get("description", "") or ""
        what_it_is = fd.get("what-it-is-2", "") or ""
        formulation_text = fd.get("formulation-3", "") or ""

        current_structure = fd.get("structure-attributes-2") or ""

        # Check if already has a formulation icon
        current_icons = set(s.strip().lower() for s in current_structure.split(",") if s.strip())
        has_formulation = bool(current_icons & FORMULATION_ICONS)

        if has_formulation:
            skipped += 1
            continue

        # First try to get from formulation-3 text field
        formulation_icon = normalize_formulation_to_icon(formulation_text)

        # If not found, infer from product info
        if not formulation_icon:
            full_text = f"{name} {product_type} {description} {what_it_is}"
            formulation_icon = infer_formulation(full_text, product_type)

        if not formulation_icon:
            skipped += 1
            continue

        # Build new structure attributes - add formulation to existing
        if current_structure:
            new_structure = f"{current_structure}, {formulation_icon}"
        else:
            new_structure = formulation_icon

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
