#!/usr/bin/env python3
"""
Fetch molecular structure images from PubChem for synthetic ingredients.
"""

import sqlite3
import requests
import time
import re
from pathlib import Path
from typing import Optional, List
from urllib.parse import quote

DB_PATH = Path(__file__).parent.parent / "data" / "ingredients.db"

PUBCHEM_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

HEADERS = {
    'User-Agent': 'iHeartClean-Bot/1.0 (ingredient research)'
}


def get_pubchem_image_url(ingredient_name: str, cas_number: str = None) -> Optional[str]:
    """
    Get molecular structure image URL from PubChem.
    Tries CAS number first, then name search.
    """
    cid = None

    # Try CAS number first (most reliable)
    if cas_number:
        try:
            url = f"{PUBCHEM_API}/compound/name/{quote(cas_number)}/cids/JSON"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                cids = data.get('IdentifierList', {}).get('CID', [])
                if cids:
                    cid = cids[0]
        except Exception:
            pass

    # Try ingredient name
    if not cid:
        # Clean up the name for search
        search_name = ingredient_name
        # Remove parenthetical common names
        search_name = re.sub(r'\s*\([^)]*\)\s*', ' ', search_name)
        # Remove common suffixes
        search_name = re.sub(r'\s+(extract|oil|water|juice|powder|butter).*$', '', search_name, flags=re.IGNORECASE)
        search_name = search_name.strip()

        if search_name:
            try:
                url = f"{PUBCHEM_API}/compound/name/{quote(search_name)}/cids/JSON"
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    cids = data.get('IdentifierList', {}).get('CID', [])
                    if cids:
                        cid = cids[0]
            except Exception:
                pass

    # If we found a CID, return the image URL
    if cid:
        # PubChem provides structure images at this URL pattern
        return f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG?image_size=300x300"

    return None


def update_structure_image(ingredient_id: int, image_url: str):
    """Update structure_image_url in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE ingredients SET structure_image_url = ? WHERE id = ?",
        (image_url, ingredient_id)
    )
    conn.commit()
    conn.close()


def get_synthetic_ingredients_without_images():
    """Get synthetic ingredients without any images."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get synthetic ingredients (not plant-based) without images
    cursor.execute('''
        SELECT id, inci_name, cas_number FROM ingredients
        WHERE (hero_image_url IS NULL AND structure_image_url IS NULL)
        AND NOT (
            inci_name LIKE '% Extract'
            OR inci_name LIKE '% Oil'
            OR inci_name LIKE '% Flower%'
            OR inci_name LIKE '% Leaf%'
            OR inci_name LIKE '% Root%'
            OR inci_name LIKE '% Seed%'
            OR inci_name LIKE '% Fruit%'
            OR inci_name LIKE '% Bark%'
            OR inci_name LIKE '% Stem%'
            OR inci_name LIKE '% Herb%'
            OR inci_name LIKE '% Bud%'
            OR inci_name LIKE '% Peel%'
            OR inci_name LIKE '% Juice'
            OR inci_name LIKE '% Butter'
            OR inci_name LIKE '% Wax'
            OR inci_name LIKE '% Water'
        )
        ORDER BY inci_name
    ''')

    results = cursor.fetchall()
    conn.close()
    return results


def fetch_pubchem_images(limit: int = None):
    """Fetch PubChem molecular structure images for synthetic ingredients."""
    ingredients = get_synthetic_ingredients_without_images()

    if limit:
        ingredients = ingredients[:limit]

    total = len(ingredients)
    print(f"Fetching PubChem images for {total} synthetic ingredients...", flush=True)

    success = 0
    failed = 0

    for i, ing in enumerate(ingredients, 1):
        inci_name = ing['inci_name']
        cas_number = ing['cas_number']

        image_url = get_pubchem_image_url(inci_name, cas_number)

        if image_url:
            update_structure_image(ing['id'], image_url)
            success += 1
        else:
            failed += 1

        if i % 100 == 0:
            print(f"  [{i}/{total}] Found: {success}, Not found: {failed}", flush=True)

        # Rate limiting - PubChem allows 5 requests/second
        time.sleep(0.25)

    print(f"\nDone! Found: {success}, Not found: {failed}", flush=True)
    return success, failed


if __name__ == "__main__":
    import sys

    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=")[1])
            except:
                pass

    fetch_pubchem_images(limit=limit)
