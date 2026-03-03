#!/usr/bin/env python3
"""
Fix format (packaging-2) and formulation (formulation-3) fields for all products.
Uses rule-based inference only (no AI) for speed.
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


def infer_format(text):
    """Infer packaging format from product text."""
    text = text.lower()

    rules = [
        ("Tube", ["tube", "squeeze tube"]),
        ("Jar", ["jar", " pot ", " tub "]),
        ("Pump", ["pump bottle", "pump dispenser", " pump"]),
        ("Stick", ["stick", "lipstick", "balm stick", "deodorant"]),
        ("Compact", ["compact", "pressed powder"]),
        ("Palette", ["palette", " quad ", "eyeshadow palette"]),
        ("Pencil", ["pencil", "eyeliner pencil", "brow pencil", "lip pencil"]),
        ("Dropper", ["dropper", "pipette", "serum bottle"]),
        ("Spray", ["spray", "mist", "spritz"]),
        ("Roll-On", ["roll-on", "rollerball"]),
        ("Pen", ["pen ", "felt tip", "marker"]),
        ("Wand", ["wand", "mascara"]),
        ("Cushion", ["cushion"]),
        ("Bottle", ["bottle"]),
        ("Brush", ["brush"]),
        ("Sponge", ["sponge", "blender"]),
    ]

    for fmt, keywords in rules:
        for kw in keywords:
            if kw in text:
                return fmt
    return None


def infer_formulation(text, product_type):
    """Infer formulation from product text and type."""
    text = text.lower()
    ptype = product_type.lower() if product_type else ""

    rules = [
        ("Cream", ["cream", "crème", "creme", "moisturizer", "night cream", "day cream"]),
        ("Serum", ["serum", "concentrate", "ampoule", "essence"]),
        ("Gel", ["gel ", " gel", "gel-cream", "jelly"]),
        ("Powder", ["powder", "pressed powder", "loose powder", "setting powder"]),
        ("Oil", [" oil ", "facial oil", "body oil", "cleansing oil", "oil-"]),
        ("Balm", ["balm", "salve", "lip balm"]),
        ("Liquid", ["liquid", "fluid"]),
        ("Mousse", ["mousse", "whip"]),
        ("Foam", ["foam", "foaming"]),
        ("Lotion", ["lotion"]),
        ("Mist", ["mist", "toner mist", "facial mist"]),
        ("Butter", ["butter", "body butter"]),
        ("Milk", ["milk", "cleansing milk"]),
        ("Clay", ["clay", "mud mask"]),
        ("Wax", ["wax", "pomade"]),
        ("Solid", ["solid", " bar "]),
        ("Emulsion", ["emulsion"]),
    ]

    for form, keywords in rules:
        for kw in keywords:
            if kw in text:
                return form

    # Infer from product type
    type_rules = {
        "serum": "Serum",
        "cream": "Cream",
        "moisturizer": "Cream",
        "cleanser": "Gel",
        "oil": "Oil",
        "mask": "Cream",
        "mist": "Mist",
        "toner": "Liquid",
        "foundation": "Liquid",
        "concealer": "Liquid",
        "lipstick": "Solid",
        "lip gloss": "Liquid",
        "mascara": "Liquid",
        "eyeshadow": "Powder",
        "blush": "Powder",
        "bronzer": "Powder",
        "highlighter": "Powder",
        "setting spray": "Mist",
        "primer": "Liquid",
    }

    for key, form in type_rules.items():
        if key in ptype:
            return form

    return None


def normalize_formulation(val):
    """Normalize existing formulation values."""
    if not val:
        return None

    val_lower = val.lower().strip()

    mappings = {
        "cream": "Cream",
        "creme": "Cream",
        "liquid": "Liquid",
        "liquid/serum": "Serum",
        "liquid serum": "Serum",
        "serum-like": "Serum",
        "serum": "Serum",
        "powder": "Powder",
        "gel": "Gel",
        "gel-oil": "Gel",
        "oil": "Oil",
        "balm": "Balm",
        "mousse": "Mousse",
        "foam": "Foam",
        "lotion": "Lotion",
        "mist": "Mist",
        "solid": "Solid",
        "wax": "Wax",
        "butter": "Butter",
    }

    for key, standard in mappings.items():
        if key in val_lower:
            return standard

    # Invalid formulations (these are finishes or other things)
    invalid = ["matte", "brush", "vegan leather", "n/a", "pencil", "powder brush"]
    for inv in invalid:
        if inv in val_lower:
            return None

    return val.title() if len(val) > 2 else None


def main():
    print("=" * 60)
    print("FIX FORMAT AND FORMULATION (Fast Mode)")
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
        description = fd.get("description", "")
        what_it_is = fd.get("what-it-is-2", "")

        current_format = fd.get("packaging-2", "")
        current_formulation = fd.get("formulation-3", "")

        # Build text for inference
        full_text = f"{name} {product_type} {description} {what_it_is}"

        # Determine what needs updating
        update_data = {}

        # Format
        if not current_format:
            inferred_format = infer_format(full_text)
            if inferred_format:
                update_data["packaging-2"] = inferred_format

        # Formulation
        normalized = normalize_formulation(current_formulation)
        if normalized and normalized != current_formulation:
            update_data["formulation-3"] = normalized
        elif not normalized:
            inferred_form = infer_formulation(full_text, product_type)
            if inferred_form:
                update_data["formulation-3"] = inferred_form

        if not update_data:
            skipped += 1
            continue

        # Update in Webflow
        try:
            resp = requests.patch(
                f"https://api.webflow.com/v2/collections/{collection_id}/items/{item_id}",
                headers=headers,
                json={"fieldData": update_data}
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
