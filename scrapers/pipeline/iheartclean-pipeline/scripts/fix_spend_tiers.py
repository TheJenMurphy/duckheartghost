#!/usr/bin/env python3
"""
Fix spend-attributes-2 field to have only ONE price tier.
Other spend icons (value-set, subscribe, sale) can remain.
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

PRICE_TIERS = {"budget", "accessible", "prestige", "luxury"}


def get_correct_tier(price):
    """Get the correct price tier based on actual price."""
    if price < 20:
        return "budget"
    elif price < 50:
        return "accessible"
    elif price < 100:
        return "prestige"
    else:
        return "luxury"


def fix_spend_attributes(spend_str, price):
    """Fix spend attributes to have only one price tier."""
    if not spend_str:
        # No spend attributes - just return the price tier
        return get_correct_tier(price)

    # Parse current values
    current = [s.strip() for s in spend_str.split(",") if s.strip()]

    # Separate price tiers from other spend icons
    other_icons = [s for s in current if s not in PRICE_TIERS]

    # Get correct price tier based on actual price
    correct_tier = get_correct_tier(price)

    # Combine: price tier first, then other icons
    result = [correct_tier] + other_icons

    return ", ".join(result)


def main():
    print("=" * 60)
    print("FIX SPEND TIERS (one price tier only)")
    print("=" * 60)

    # Get all products
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

    print(f"\nFound {len(all_items)} products")

    # Find products that need fixing
    to_fix = []
    for item in all_items:
        fd = item.get("fieldData", {})
        spend = fd.get("spend-attributes-2", "")
        price = fd.get("product-price", 0) or 0

        # Check if multiple price tiers exist
        current_tiers = [s.strip() for s in spend.split(",") if s.strip() in PRICE_TIERS]
        if len(current_tiers) > 1:
            to_fix.append({
                "id": item["id"],
                "name": fd.get("name", "Unknown"),
                "price": price,
                "current_spend": spend,
                "fixed_spend": fix_spend_attributes(spend, price)
            })

    print(f"Products with multiple price tiers: {len(to_fix)}")

    if not to_fix:
        print("\nNo products need fixing!")
        return

    # Show what will be fixed
    print("\nProducts to fix:")
    for p in to_fix[:10]:
        print(f"  ${p['price']:>6.0f} | {p['name'][:30]:<30}")
        print(f"         Current: {p['current_spend']}")
        print(f"         Fixed:   {p['fixed_spend']}")

    if len(to_fix) > 10:
        print(f"  ... and {len(to_fix) - 10} more")

    # Confirm
    print(f"\nReady to update {len(to_fix)} products? (y/n): ", end="")
    confirm = input().strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    # Update products
    print("\nUpdating products...")
    success = 0
    failed = 0

    for i, p in enumerate(to_fix, 1):
        try:
            resp = requests.patch(
                f"https://api.webflow.com/v2/collections/{collection_id}/items/{p['id']}",
                headers=headers,
                json={"fieldData": {"spend-attributes-2": p["fixed_spend"]}}
            )
            resp.raise_for_status()
            print(f"  [{i}/{len(to_fix)}] Fixed: {p['name'][:40]}")
            success += 1
        except Exception as e:
            print(f"  [{i}/{len(to_fix)}] FAILED: {p['name'][:40]} - {e}")
            failed += 1

        time.sleep(0.3)  # Rate limiting

    print(f"\n{'=' * 60}")
    print(f"COMPLETE: {success} fixed, {failed} failed")
    print("=" * 60)


if __name__ == "__main__":
    main()
