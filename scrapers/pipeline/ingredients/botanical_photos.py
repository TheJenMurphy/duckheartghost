#!/usr/bin/env python3
"""
Fetch botanical photos from Wikimedia Commons for plant-based ingredients.
Uses Wikipedia REST API and Commons search to find images.
"""

import sqlite3
import requests
import time
import re
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "ingredients.db"

# User agent required by Wikimedia API
HEADERS = {
    'User-Agent': 'iHeartClean-Bot/1.0 (ingredient research; contact@example.com)'
}

def extract_latin_name(inci_name: str) -> Optional[str]:
    """
    Extract the Latin botanical name from an INCI name.
    INCI format is typically: "Genus Species Extract/Oil/etc"
    e.g., "Lavandula Angustifolia Flower Extract" -> "Lavandula angustifolia"
    """
    if not inci_name:
        return None

    # Common INCI suffixes to remove
    suffixes = [
        'extract', 'oil', 'water', 'juice', 'powder', 'butter', 'wax',
        'flower', 'leaf', 'root', 'seed', 'fruit', 'bark', 'stem',
        'peel', 'kernel', 'shell', 'bud', 'herb', 'whole', 'plant',
        'callus', 'cell', 'culture', 'filtrate', 'meristem',
    ]

    # Split the name and find potential genus/species
    words = inci_name.split()

    if len(words) < 2:
        return None

    # First two words are typically Genus Species
    genus = words[0]
    species = words[1].lower()

    # Check if second word looks like a species (not a part or product type)
    if species in suffixes:
        return None

    # Basic validation - genus should be capitalized, species lowercase in output
    if not genus[0].isupper():
        return None

    # Return formatted Latin name
    return f"{genus} {species}"


def search_wikimedia_image(search_term: str) -> Optional[str]:
    """
    Search for an image on Wikimedia Commons.
    Uses Wikipedia REST API to find media for the page.
    """
    if not search_term:
        return None

    # Try Wikipedia REST API first
    encoded_term = search_term.replace(' ', '_')
    url = f"https://en.wikipedia.org/api/rest_v1/page/media-list/{encoded_term}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])

            # Look for a good image (prefer jpg/png, avoid svg/icons)
            for item in items:
                if item.get('type') == 'image':
                    src = item.get('srcset', [])
                    if src:
                        # Get highest resolution
                        best = max(src, key=lambda x: x.get('scale', 0))
                        img_url = best.get('src', '')
                        if img_url:
                            # Convert to full URL
                            if img_url.startswith('//'):
                                img_url = 'https:' + img_url
                            # Skip small icons/diagrams
                            if 'icon' not in img_url.lower() and 'logo' not in img_url.lower():
                                return img_url
    except Exception as e:
        pass

    # Fallback: Try Commons search
    try:
        commons_url = "https://commons.wikimedia.org/w/api.php"
        params = {
            'action': 'query',
            'format': 'json',
            'list': 'search',
            'srsearch': f'"{search_term}" filetype:bitmap',
            'srnamespace': '6',  # File namespace
            'srlimit': '5'
        }
        resp = requests.get(commons_url, params=params, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('query', {}).get('search', [])

            if results:
                # Get the first result's file info
                title = results[0].get('title', '')
                if title:
                    # Get the actual image URL
                    info_params = {
                        'action': 'query',
                        'format': 'json',
                        'titles': title,
                        'prop': 'imageinfo',
                        'iiprop': 'url',
                        'iiurlwidth': '800'  # Request a reasonably sized thumbnail
                    }
                    info_resp = requests.get(commons_url, params=info_params, headers=HEADERS, timeout=10)
                    if info_resp.status_code == 200:
                        info_data = info_resp.json()
                        pages = info_data.get('query', {}).get('pages', {})
                        for page in pages.values():
                            imageinfo = page.get('imageinfo', [])
                            if imageinfo:
                                return imageinfo[0].get('thumburl') or imageinfo[0].get('url')
    except Exception as e:
        pass

    return None


def get_plant_ingredients():
    """Get all plant-based ingredients from the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query for plant-based ingredients based on INCI naming patterns
    cursor.execute("""
        SELECT id, inci_name, common_names
        FROM ingredients
        WHERE inci_name LIKE '% Extract'
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
        ORDER BY inci_name
    """)

    results = cursor.fetchall()
    conn.close()
    return results


def update_hero_image(ingredient_id: int, image_url: str):
    """Update the hero_image_url for an ingredient."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE ingredients SET hero_image_url = ? WHERE id = ?",
        (image_url, ingredient_id)
    )
    conn.commit()
    conn.close()


def fetch_botanical_photos(limit: int = None, skip_existing: bool = True):
    """
    Fetch botanical photos for plant-based ingredients.

    Args:
        limit: Maximum number of ingredients to process (None for all)
        skip_existing: Skip ingredients that already have a hero image
    """
    ingredients = get_plant_ingredients()

    if skip_existing:
        # Filter out ingredients that already have images
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM ingredients WHERE hero_image_url IS NOT NULL")
        existing_ids = {row[0] for row in cursor.fetchall()}
        conn.close()

        ingredients = [i for i in ingredients if i['id'] not in existing_ids]

    if limit:
        ingredients = ingredients[:limit]

    total = len(ingredients)
    print(f"Fetching botanical photos for {total} plant-based ingredients...")

    success = 0
    failed = 0

    for i, ing in enumerate(ingredients, 1):
        inci_name = ing['inci_name']
        latin_name = extract_latin_name(inci_name)

        image_url = None
        search_term = None

        # Try Latin name first
        if latin_name:
            search_term = latin_name
            image_url = search_wikimedia_image(latin_name)

        # Fall back to common name if available
        if not image_url and ing['common_names']:
            # common_names might be comma-separated, use the first one
            common = ing['common_names'].split(',')[0].strip()
            search_term = common
            image_url = search_wikimedia_image(common)

        if image_url:
            update_hero_image(ing['id'], image_url)
            success += 1
        else:
            failed += 1

        # Progress update every 50 ingredients
        if i % 50 == 0:
            print(f"  [{i}/{total}] Found: {success}, Not found: {failed}")

        # Rate limiting - be respectful to Wikimedia
        time.sleep(0.5)

    print(f"\nDone! Found images for {success} ingredients, {failed} not found.")
    return success, failed


if __name__ == "__main__":
    import sys

    # Check for command line args
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass

    fetch_botanical_photos(limit=limit)
