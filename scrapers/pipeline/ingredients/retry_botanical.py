#!/usr/bin/env python3
"""
Retry fetching botanical photos for plant-based ingredients without images.
Uses multiple search strategies including common names.
"""

import sqlite3
import requests
import time
import re
from pathlib import Path
from typing import Optional, List

DB_PATH = Path(__file__).parent.parent / "data" / "ingredients.db"

HEADERS = {
    'User-Agent': 'iHeartClean-Bot/1.0 (ingredient research)'
}


def extract_search_terms(inci_name: str) -> List[str]:
    """
    Extract multiple search terms from INCI name.
    Returns list of terms to try in order.
    """
    terms = []

    # 1. Try to extract common name from parentheses
    # e.g., "simmondsia chinensis (jojoba) seed oil" -> "jojoba"
    common_match = re.search(r'\(([^)]+)\)', inci_name)
    if common_match:
        common_name = common_match.group(1).strip()
        # Clean up common name
        common_name = re.sub(r'\s+(oil|extract|butter|wax|water|juice).*', '', common_name, flags=re.IGNORECASE)
        if len(common_name) > 2:
            terms.append(common_name)

    # 2. Extract Latin name (first two words, typically Genus species)
    words = inci_name.split()
    if len(words) >= 2:
        genus = words[0]
        species = words[1].lower()

        # Skip if second word is a common suffix
        skip_words = ['seed', 'leaf', 'root', 'flower', 'fruit', 'bark', 'oil', 'extract', 'butter', 'wax']
        if species not in skip_words and not species.startswith('('):
            latin_name = f"{genus.capitalize()} {species}"
            terms.append(latin_name)

    # 3. Try just the genus
    if words:
        genus = words[0].capitalize()
        if len(genus) > 3 and genus.lower() not in ['the', 'and', 'hydrolyzed']:
            terms.append(genus)

    return terms


def search_wikimedia_image(search_term: str) -> Optional[str]:
    """Search for an image on Wikimedia Commons."""
    if not search_term:
        return None

    # Try Wikipedia REST API
    encoded_term = search_term.replace(' ', '_')
    url = f"https://en.wikipedia.org/api/rest_v1/page/media-list/{encoded_term}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])

            for item in items:
                if item.get('type') == 'image':
                    src = item.get('srcset', [])
                    if src:
                        best = max(src, key=lambda x: x.get('scale', 0))
                        img_url = best.get('src', '')
                        if img_url:
                            if img_url.startswith('//'):
                                img_url = 'https:' + img_url
                            if 'icon' not in img_url.lower() and 'logo' not in img_url.lower():
                                return img_url
    except Exception:
        pass

    # Fallback: Commons search
    try:
        commons_url = "https://commons.wikimedia.org/w/api.php"
        params = {
            'action': 'query',
            'format': 'json',
            'list': 'search',
            'srsearch': f'"{search_term}" filetype:bitmap',
            'srnamespace': '6',
            'srlimit': '5'
        }
        resp = requests.get(commons_url, params=params, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('query', {}).get('search', [])

            if results:
                title = results[0].get('title', '')
                if title:
                    info_params = {
                        'action': 'query',
                        'format': 'json',
                        'titles': title,
                        'prop': 'imageinfo',
                        'iiprop': 'url',
                        'iiurlwidth': '800'
                    }
                    info_resp = requests.get(commons_url, params=info_params, headers=HEADERS, timeout=10)
                    if info_resp.status_code == 200:
                        info_data = info_resp.json()
                        pages = info_data.get('query', {}).get('pages', {})
                        for page in pages.values():
                            imageinfo = page.get('imageinfo', [])
                            if imageinfo:
                                return imageinfo[0].get('thumburl') or imageinfo[0].get('url')
    except Exception:
        pass

    return None


def update_hero_image(ingredient_id: int, image_url: str):
    """Update hero_image_url in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE ingredients SET hero_image_url = ? WHERE id = ?",
        (image_url, ingredient_id)
    )
    conn.commit()
    conn.close()


def get_plant_ingredients_without_images():
    """Get plant-based ingredients that have no images."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, inci_name FROM ingredients
        WHERE (hero_image_url IS NULL AND structure_image_url IS NULL)
        AND (
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


def retry_botanical_photos():
    """Retry fetching botanical photos with enhanced search."""
    ingredients = get_plant_ingredients_without_images()
    total = len(ingredients)

    print(f"Retrying {total} plant-based ingredients without images...", flush=True)

    success = 0
    failed = 0

    for i, ing in enumerate(ingredients, 1):
        inci_name = ing['inci_name']
        search_terms = extract_search_terms(inci_name)

        image_url = None
        used_term = None

        # Try each search term
        for term in search_terms:
            image_url = search_wikimedia_image(term)
            if image_url:
                used_term = term
                break
            time.sleep(0.3)  # Rate limit between attempts

        if image_url:
            update_hero_image(ing['id'], image_url)
            success += 1
        else:
            failed += 1

        if i % 50 == 0:
            print(f"  [{i}/{total}] Found: {success}, Not found: {failed}", flush=True)

        time.sleep(0.2)

    print(f"\nDone! Found: {success}, Not found: {failed}", flush=True)
    return success, failed


if __name__ == "__main__":
    retry_botanical_photos()
