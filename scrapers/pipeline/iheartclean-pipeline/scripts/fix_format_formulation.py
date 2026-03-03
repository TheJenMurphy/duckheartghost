#!/usr/bin/env python3
"""
Fix format (packaging-2) and formulation (formulation-3) fields for all products.
Uses AI to infer missing values from product name and type.
"""

import os
import time
import requests
import re
from dotenv import load_dotenv

load_dotenv()

api_token = os.environ.get("WEBFLOW_API_TOKEN")
collection_id = os.environ.get("WEBFLOW_COLLECTION_ID")
anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json",
    "accept": "application/json",
}

# Valid format values
VALID_FORMATS = [
    "Tube", "Jar", "Bottle", "Pump", "Stick", "Compact", "Palette",
    "Pencil", "Dropper", "Spray", "Roll-On", "Pot", "Pen", "Wand",
    "Cushion", "Refill", "Sachet", "Applicator", "Brush", "Tool"
]

# Valid formulation values
VALID_FORMULATIONS = [
    "Liquid", "Cream", "Gel", "Powder", "Oil", "Serum", "Balm",
    "Mousse", "Foam", "Butter", "Lotion", "Mist", "Wax", "Solid",
    "Emulsion", "Essence", "Milk", "Water", "Clay", "Paste"
]


def infer_format_formulation(name, product_type, description):
    """Use simple rules to infer format and formulation from product info."""
    text = f"{name} {product_type} {description}".lower()

    # Infer format
    format_val = None
    format_rules = {
        "Tube": ["tube", "squeeze"],
        "Jar": ["jar", "pot", "tub"],
        "Bottle": ["bottle"],
        "Pump": ["pump"],
        "Stick": ["stick", "balm stick", "lipstick"],
        "Compact": ["compact", "pressed"],
        "Palette": ["palette", "quad"],
        "Pencil": ["pencil", "liner pencil", "brow pencil"],
        "Dropper": ["dropper", "pipette"],
        "Spray": ["spray", "mist bottle", "spritz"],
        "Roll-On": ["roll-on", "rollerball"],
        "Pot": ["pot"],
        "Pen": ["pen", "click pen", "felt tip"],
        "Wand": ["wand", "mascara"],
        "Cushion": ["cushion", "cushion compact"],
        "Brush": ["brush"],
        "Tool": ["tool", "sponge", "applicator"],
    }

    for fmt, keywords in format_rules.items():
        for kw in keywords:
            if kw in text:
                format_val = fmt
                break
        if format_val:
            break

    # Infer formulation
    formulation_val = None
    formulation_rules = {
        "Liquid": ["liquid", "fluid"],
        "Cream": ["cream", "creme", "crème"],
        "Gel": ["gel", "gel-cream", "jelly"],
        "Powder": ["powder", "pressed powder", "loose powder"],
        "Oil": ["oil", "facial oil", "body oil"],
        "Serum": ["serum", "concentrate"],
        "Balm": ["balm", "salve"],
        "Mousse": ["mousse", "whip"],
        "Foam": ["foam", "foaming"],
        "Butter": ["butter", "body butter"],
        "Lotion": ["lotion"],
        "Mist": ["mist", "spray", "toner mist"],
        "Wax": ["wax", "pomade"],
        "Solid": ["solid", "bar", "stick"],
        "Emulsion": ["emulsion"],
        "Essence": ["essence"],
        "Milk": ["milk", "cleansing milk"],
        "Water": ["water", "micellar"],
        "Clay": ["clay", "mud"],
        "Paste": ["paste"],
    }

    for form, keywords in formulation_rules.items():
        for kw in keywords:
            if kw in text:
                formulation_val = form
                break
        if formulation_val:
            break

    return format_val, formulation_val


def infer_with_ai(name, product_type, description, what_it_is):
    """Use Claude to infer format and formulation when rules fail."""
    if not anthropic_key:
        return None, None

    prompt = f"""Given this beauty product, determine its packaging FORMAT and FORMULATION.

Product: {name}
Type: {product_type}
Description: {what_it_is or description}

Valid FORMATS: {', '.join(VALID_FORMATS)}
Valid FORMULATIONS: {', '.join(VALID_FORMULATIONS)}

Respond with ONLY two words separated by a comma, e.g.: "Tube, Cream"
If you can't determine one, use "Unknown" for that value.
"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 50,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=10
        )
        resp.raise_for_status()

        answer = resp.json()["content"][0]["text"].strip()
        parts = [p.strip() for p in answer.split(",")]

        fmt = parts[0] if len(parts) > 0 and parts[0] in VALID_FORMATS else None
        form = parts[1] if len(parts) > 1 and parts[1] in VALID_FORMULATIONS else None

        return fmt, form
    except Exception as e:
        return None, None


def normalize_formulation(val):
    """Normalize existing formulation values."""
    if not val:
        return None

    val_lower = val.lower().strip()

    # Map variations to standard values
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
        "matte": None,  # This is a finish, not formulation
        "brush": None,  # This is a tool
        "vegan leather": None,  # This is material
        "n/a": None,
    }

    for key, standard in mappings.items():
        if key in val_lower:
            return standard

    # If it's already a valid value, capitalize it
    for valid in VALID_FORMULATIONS:
        if val_lower == valid.lower():
            return valid

    return None


def main():
    print("=" * 60)
    print("FIX FORMAT AND FORMULATION FIELDS")
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
    ai_calls = 0

    for i, item in enumerate(all_items, 1):
        fd = item.get("fieldData", {})
        item_id = item["id"]
        name = fd.get("name", "")
        product_type = fd.get("product-type-3", "")
        description = fd.get("description", "")
        what_it_is = fd.get("what-it-is-2", "")

        current_format = fd.get("packaging-2", "")
        current_formulation = fd.get("formulation-3", "")

        # Normalize existing formulation
        normalized_formulation = normalize_formulation(current_formulation)

        # Check if we need to update
        needs_format = not current_format
        needs_formulation = not normalized_formulation

        if not needs_format and not needs_formulation:
            if normalized_formulation != current_formulation:
                # Just normalize the formulation
                pass
            else:
                skipped += 1
                continue

        # Try rule-based inference first
        inferred_format, inferred_formulation = infer_format_formulation(
            name, product_type, f"{description} {what_it_is}"
        )

        # Use AI if rules didn't work
        if (needs_format and not inferred_format) or (needs_formulation and not inferred_formulation):
            if anthropic_key and ai_calls < 500:  # Limit AI calls
                ai_format, ai_formulation = infer_with_ai(name, product_type, description, what_it_is)
                if not inferred_format:
                    inferred_format = ai_format
                if not inferred_formulation:
                    inferred_formulation = ai_formulation
                ai_calls += 1
                time.sleep(0.1)  # Rate limit AI calls

        # Build update
        update_data = {}

        if needs_format and inferred_format:
            update_data["packaging-2"] = inferred_format

        if needs_formulation and inferred_formulation:
            update_data["formulation-3"] = inferred_formulation
        elif normalized_formulation and normalized_formulation != current_formulation:
            update_data["formulation-3"] = normalized_formulation

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

            if i % 100 == 0 or i == len(all_items):
                print(f"   [{i}/{len(all_items)}] Updated: {updated}, AI calls: {ai_calls}")

        except Exception as e:
            print(f"   FAILED: {name[:30]} - {e}")
            failed += 1

        time.sleep(0.2)

    print(f"\n{'=' * 60}")
    print("COMPLETE")
    print("=" * 60)
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")
    print(f"  AI calls used: {ai_calls}")


if __name__ == "__main__":
    main()
