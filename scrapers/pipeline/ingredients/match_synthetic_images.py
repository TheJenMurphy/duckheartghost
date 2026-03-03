#!/usr/bin/env python3
"""
Match remaining synthetic ingredients to plant/mineral images.

This script:
1. Loads synthetic ingredients from Webflow that don't have gallery images
2. Extracts meaningful keywords (plant names, minerals, etc.) from ingredient names
3. Matches to image folders, avoiding generic terms
4. Outputs matches for syncing to Webflow

Usage:
    python match_synthetic_images.py
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import requests

# Configuration
WEBFLOW_API_BASE = "https://api.webflow.com/v2"
PROJECT_DIR = Path(__file__).parent.parent.parent
OUTPUT_FILE = PROJECT_DIR / "synthetic_image_matches.json"

# Image folders
GDRIVE_MASTER_PATH = Path("/Users/jenmurphy/Library/CloudStorage/GoogleDrive-hello@iheartclean.beauty/My Drive/Ingredient Images/master")

# Keywords to SKIP - too generic or not visually meaningful
SKIP_KEYWORDS = {
    # Generic chemistry terms
    'acid', 'ester', 'esters', 'ether', 'oxide', 'hydroxide', 'chloride',
    'sulfate', 'phosphate', 'carbonate', 'nitrate', 'acetate', 'lactate',
    'citrate', 'gluconate', 'succinate', 'tartrate', 'benzoate', 'sorbate',
    'polymer', 'copolymer', 'crosspolymer', 'resin', 'silicone', 'silicate',

    # Generic product terms
    'extract', 'water', 'oil', 'butter', 'wax', 'powder', 'flour', 'starch',
    'protein', 'peptide', 'amino', 'vitamin', 'mineral', 'complex',
    'ferment', 'lysate', 'filtrate', 'hydrolysate', 'distillate',

    # Process terms
    'hydrolyzed', 'hydrogenated', 'modified', 'treated', 'processed',

    # Size/number terms
    'mono', 'di', 'tri', 'tetra', 'penta', 'hexa', 'poly', 'oligo',

    # Common suffixes
    'ate', 'ide', 'ine', 'ose', 'ase', 'ene', 'ane', 'one', 'ol',
}

# Specific ingredient-to-source mappings for common synthetics
INGREDIENT_TO_SOURCE = {
    # Safflower derivatives
    'safflower': ['Safflower', 'Carthamus Tinctorius'],
    'safflowerate': ['Safflower', 'Carthamus Tinctorius'],

    # Mineral/Metal sources
    'zinc': ['Zinc'],
    'copper': ['Copper'],
    'iron': ['Iron'],
    'magnesium': ['Magnesium'],
    'calcium': ['Calcium'],
    'potassium': ['Potassium'],
    'sodium': ['Salt', 'Sodium'],
    'silver': ['Silver'],
    'gold': ['Gold'],
    'titanium': ['Titanium'],
    'aluminum': ['Aluminum'],
    'silica': ['Silica'],
    'sulfur': ['Sulfur'],
    'selenium': ['Selenium'],
    'manganese': ['Manganese'],

    # Plant sources
    'coconut': ['Coconut', 'Cocos Nucifera'],
    'coco': ['Coconut', 'Cocos Nucifera'],
    'palm': ['Palm'],
    'olive': ['Olive', 'Olea Europaea'],
    'sunflower': ['Sunflower', 'Helianthus Annuus'],
    'soy': ['Soy', 'Soybean', 'Glycine Max'],
    'soya': ['Soy', 'Soybean', 'Glycine Max'],
    'corn': ['Corn', 'Zea Mays'],
    'maize': ['Corn', 'Zea Mays'],
    'wheat': ['Wheat', 'Triticum'],
    'rice': ['Rice', 'Oryza Sativa'],
    'oat': ['Oat', 'Avena Sativa'],
    'barley': ['Barley', 'Hordeum Vulgare'],
    'almond': ['Almond', 'Prunus Dulcis'],
    'shea': ['Shea', 'Shea Butter'],
    'cocoa': ['Cocoa', 'Cacao', 'Theobroma Cacao'],
    'cacao': ['Cocoa', 'Cacao', 'Theobroma Cacao'],
    'avocado': ['Avocado', 'Persea Gratissima'],
    'jojoba': ['Jojoba', 'Simmondsia Chinensis'],
    'argan': ['Argan', 'Argania Spinosa'],
    'castor': ['Castor', 'Ricinus Communis'],
    'sesame': ['Sesame', 'Sesamum Indicum'],
    'grape': ['Grape', 'Vitis Vinifera'],
    'apple': ['Apple', 'Malus Domestica'],
    'lemon': ['Lemon', 'Citrus Limon'],
    'orange': ['Orange', 'Citrus Sinensis'],
    'lime': ['Lime', 'Citrus Aurantifolia'],
    'grapefruit': ['Grapefruit', 'Citrus Paradisi'],
    'bergamot': ['Bergamot', 'Citrus Bergamia'],
    'mandarin': ['Mandarin', 'Citrus Nobilis'],
    'tangerine': ['Tangerine', 'Citrus Tangerina'],
    'rose': ['Rose', 'Rosa'],
    'lavender': ['Lavender', 'Lavandula'],
    'chamomile': ['Chamomile', 'Matricaria'],
    'tea': ['Tea', 'Camellia Sinensis', 'Green Tea'],
    'coffee': ['Coffee', 'Coffea'],
    'vanilla': ['Vanilla', 'Vanilla Planifolia'],
    'honey': ['Honey', 'Mel'],
    'beeswax': ['Beeswax'],
    'lanolin': ['Lanolin'],
    'milk': ['Milk'],
    'yogurt': ['Yogurt'],
    'aloe': ['Aloe', 'Aloe Vera'],
    'ginger': ['Ginger', 'Zingiber'],
    'turmeric': ['Turmeric', 'Curcuma Longa'],
    'cinnamon': ['Cinnamon', 'Cinnamomum'],
    'mint': ['Mint', 'Mentha'],
    'peppermint': ['Peppermint', 'Mentha Piperita'],
    'spearmint': ['Spearmint', 'Mentha Spicata'],
    'eucalyptus': ['Eucalyptus'],
    'rosemary': ['Rosemary', 'Rosmarinus'],
    'thyme': ['Thyme', 'Thymus'],
    'sage': ['Sage', 'Salvia'],
    'basil': ['Basil', 'Ocimum'],
    'oregano': ['Oregano', 'Origanum'],
    'clove': ['Clove', 'Eugenia Caryophyllus'],
    'nutmeg': ['Nutmeg', 'Myristica'],
    'cardamom': ['Cardamom', 'Elettaria'],
    'fennel': ['Fennel', 'Foeniculum'],
    'anise': ['Anise', 'Pimpinella'],
    'licorice': ['Licorice', 'Glycyrrhiza'],
    'ginseng': ['Ginseng', 'Panax'],
    'bamboo': ['Bamboo'],
    'cotton': ['Cotton', 'Gossypium'],
    'hemp': ['Hemp', 'Cannabis'],
    'flax': ['Flax', 'Linum'],
    'chia': ['Chia', 'Salvia Hispanica'],
    'quinoa': ['Quinoa', 'Chenopodium'],
    'seaweed': ['Seaweed', 'Algae'],
    'kelp': ['Kelp', 'Laminaria'],
    'spirulina': ['Spirulina'],
    'chlorella': ['Chlorella'],
    'carrot': ['Carrot', 'Daucus Carota'],
    'tomato': ['Tomato', 'Solanum Lycopersicum'],
    'cucumber': ['Cucumber', 'Cucumis Sativus'],
    'potato': ['Potato', 'Solanum Tuberosum'],
    'beet': ['Beet', 'Beta Vulgaris'],
    'spinach': ['Spinach', 'Spinacia'],
    'kale': ['Kale', 'Brassica Oleracea'],
    'broccoli': ['Broccoli', 'Brassica'],
    'cabbage': ['Cabbage', 'Brassica'],
    'garlic': ['Garlic', 'Allium Sativum'],
    'onion': ['Onion', 'Allium Cepa'],
    'berry': ['Berry'],
    'strawberry': ['Strawberry', 'Fragaria'],
    'blueberry': ['Blueberry', 'Vaccinium'],
    'raspberry': ['Raspberry', 'Rubus Idaeus'],
    'blackberry': ['Blackberry', 'Rubus'],
    'cranberry': ['Cranberry', 'Vaccinium Macrocarpon'],
    'acai': ['Acai', 'Euterpe Oleracea'],
    'pomegranate': ['Pomegranate', 'Punica Granatum'],
    'mango': ['Mango', 'Mangifera Indica'],
    'papaya': ['Papaya', 'Carica Papaya'],
    'pineapple': ['Pineapple', 'Ananas'],
    'banana': ['Banana', 'Musa'],
    'coconut': ['Coconut', 'Cocos Nucifera'],
    'peach': ['Peach', 'Prunus Persica'],
    'apricot': ['Apricot', 'Prunus Armeniaca'],
    'plum': ['Plum', 'Prunus Domestica'],
    'cherry': ['Cherry', 'Prunus Cerasus'],
    'fig': ['Fig', 'Ficus Carica'],
    'date': ['Date', 'Phoenix Dactylifera'],
    'walnut': ['Walnut', 'Juglans'],
    'hazelnut': ['Hazelnut', 'Corylus'],
    'macadamia': ['Macadamia'],
    'pistachio': ['Pistachio', 'Pistacia'],
    'cashew': ['Cashew', 'Anacardium'],
    'peanut': ['Peanut', 'Arachis'],
    'watermelon': ['Watermelon', 'Citrullus'],
    'melon': ['Melon', 'Cucumis Melo'],
    'cantaloupe': ['Cantaloupe', 'Cucumis Melo'],
    'kiwi': ['Kiwi', 'Actinidia'],
    'passion': ['Passion Fruit', 'Passiflora'],
    'guava': ['Guava', 'Psidium'],
    'lychee': ['Lychee', 'Litchi'],
    'dragon': ['Dragon Fruit', 'Hylocereus'],
    'xanthan': ['Xanthan Gum'],
    'carrageenan': ['Carrageenan', 'Irish Moss'],
    'agar': ['Agar'],
    'pectin': ['Pectin'],
    'gelatin': ['Gelatin'],
    'collagen': ['Collagen'],
    'keratin': ['Keratin'],
    'silk': ['Silk'],
    'pearl': ['Pearl'],
    'charcoal': ['Charcoal', 'Activated Charcoal'],
    'clay': ['Clay', 'Kaolin'],
    'kaolin': ['Kaolin', 'Clay'],
    'bentonite': ['Bentonite', 'Clay'],
    'mica': ['Mica'],
    'talc': ['Talc'],
}

# Natural image keywords (prefer these)
NATURAL_IMAGE_KEYWORDS = [
    'wild', 'field', 'garden', 'farm', 'outdoor', 'nature', 'plant', 'tree',
    'flower', 'leaf', 'fruit', 'seed', 'root', 'herb', 'growing', 'fresh',
    'harvest', 'organic', 'natural', 'raw', 'close', 'macro', 'dreamstime',
    'adobestock', 'adobe', 'stock', 'xxl', 'full', 'pretty'
]

# Studio image keywords (avoid these)
STUDIO_IMAGE_KEYWORDS = [
    'white', 'background', 'isolated', 'studio', 'bottle', 'jar', 'container',
    'product', 'cosmetic', 'cream', 'lotion', 'serum', 'oil-bottle', 'dropper',
    'square', 'icon', 'logo', 'banner', 'page', 'glossary'
]


def normalize_name(name: str) -> str:
    """Normalize a name for matching."""
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    return name


def extract_source_keywords(ingredient_name: str) -> List[str]:
    """Extract meaningful source keywords from ingredient name."""
    sources = []
    name_lower = ingredient_name.lower()

    # Check direct mappings first
    for keyword, source_list in INGREDIENT_TO_SOURCE.items():
        # Use word boundary matching
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, name_lower):
            sources.extend(source_list)

    # Also extract words that might be plant/mineral names
    # but filter out generic chemistry terms
    words = re.findall(r'[a-z]{4,}', name_lower)
    for word in words:
        if word not in SKIP_KEYWORDS and word not in [s.lower() for s in sources]:
            # Check if it might be a plant genus (capitalized in original)
            if re.search(r'\b' + word.capitalize() + r'\b', ingredient_name):
                sources.append(word.capitalize())

    # Remove duplicates while preserving order
    seen = set()
    unique_sources = []
    for s in sources:
        s_lower = s.lower()
        if s_lower not in seen:
            seen.add(s_lower)
            unique_sources.append(s)

    return unique_sources


def load_image_folders() -> Dict[str, Path]:
    """Load available image folders and their paths."""
    folders = {}

    if not GDRIVE_MASTER_PATH.exists():
        print(f"Warning: Image folder not found: {GDRIVE_MASTER_PATH}")
        return folders

    for folder in GDRIVE_MASTER_PATH.iterdir():
        if folder.is_dir():
            norm_name = normalize_name(folder.name)
            folders[norm_name] = folder

            # Also store by significant words
            for part in norm_name.split():
                if len(part) > 3 and part not in SKIP_KEYWORDS:
                    if part not in folders:
                        folders[part] = folder

    return folders


def find_matching_folders(sources: List[str], all_folders: Dict[str, Path]) -> List[Path]:
    """Find image folders that match source keywords."""
    matches = []
    seen_paths = set()

    for source in sources:
        norm_source = normalize_name(source)

        # Direct match
        if norm_source in all_folders:
            path = all_folders[norm_source]
            if path not in seen_paths:
                matches.append(path)
                seen_paths.add(path)

        # Partial match - source in folder name
        for folder_name, folder_path in all_folders.items():
            if folder_path in seen_paths:
                continue

            if norm_source in folder_name or folder_name in norm_source:
                if len(norm_source) > 3 and len(folder_name) > 3:  # Avoid tiny matches
                    matches.append(folder_path)
                    seen_paths.add(folder_path)

            if len(matches) >= 10:
                break

        if len(matches) >= 10:
            break

    return matches


def get_images_from_folders(folders: List[Path]) -> List[str]:
    """Get image files from matched folders, prioritizing natural images."""
    all_images = []

    for folder in folders:
        if not folder.exists():
            continue

        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                all_images.append(str(f))

    # Score and sort images
    def score_image(path: str) -> Tuple[int, int, str]:
        fname = Path(path).stem.lower()
        ext = Path(path).suffix.lower()

        natural_score = sum(1 for kw in NATURAL_IMAGE_KEYWORDS if kw in fname)
        studio_score = sum(1 for kw in STUDIO_IMAGE_KEYWORDS if kw in fname)
        ext_score = 0 if ext in ['.jpg', '.jpeg'] else 1

        return (-natural_score + studio_score, ext_score, fname)

    all_images.sort(key=score_image)
    return all_images[:10]


def load_webflow_ingredients():
    """Load synthetic ingredients without gallery images from Webflow."""
    api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
    collection_id = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')

    if not api_token or not collection_id:
        raise ValueError("WEBFLOW_API_TOKEN and WEBFLOW_INGREDIENTS_COLLECTION_ID required")

    session = requests.Session()
    session.headers.update({
        'Authorization': f'Bearer {api_token}',
        'Accept': 'application/json',
    })

    print("Loading ingredients from Webflow...")
    items = []
    offset = 0

    while True:
        resp = session.get(
            f'{WEBFLOW_API_BASE}/collections/{collection_id}/items?limit=100&offset={offset}'
        )
        if not resp.ok:
            print(f"Error: {resp.status_code} - {resp.text[:200]}")
            break

        data = resp.json()
        batch = data.get('items', [])
        if not batch:
            break

        items.extend(batch)
        print(f"  Loaded {len(items)}...", end='\r')

        if len(batch) < 100:
            break
        offset += 100

    print(f"  Loaded {len(items)} total ingredients")

    # Filter to synthetic without gallery images
    type_field = 'type-i-e-mineral-vitamin-botanical-synthetic-plant-derived-synthetic'
    filtered = []

    for item in items:
        fd = item.get('fieldData', {})
        ingredient_type = fd.get(type_field, '')

        # Only synthetic
        if ingredient_type != 'synthetic':
            continue

        # Skip if already has gallery images
        if fd.get('in-the-field-image', {}).get('url'):
            continue

        filtered.append({
            'id': item.get('id'),
            'name': fd.get('name', ''),
            'slug': fd.get('slug', '')
        })

    print(f"  Found {len(filtered)} synthetic ingredients without gallery images")
    return filtered


def main():
    print("=" * 70)
    print("SYNTHETIC INGREDIENT IMAGE MATCHER")
    print("=" * 70)
    print()

    # Load image folders
    print("Loading image folders...")
    all_folders = load_image_folders()
    print(f"  Found {len(all_folders)} folder name mappings")
    print()

    # Load ingredients
    ingredients = load_webflow_ingredients()
    print()

    # Match ingredients to images
    print("Matching ingredients to images...")
    matches = []
    matched_count = 0

    for i, ing in enumerate(ingredients, 1):
        name = ing['name']

        # Extract source keywords
        sources = extract_source_keywords(name)

        if not sources:
            continue

        # Find matching folders
        folders = find_matching_folders(sources, all_folders)

        if folders:
            # Get images from folders
            images = get_images_from_folders(folders)

            if images:
                matched_count += 1
                matches.append({
                    'id': ing['id'],
                    'ingredient': name,
                    'slug': ing['slug'],
                    'source_keywords': sources[:5],
                    'matched_folders': [f.name for f in folders[:5]],
                    'all_images': images
                })

                if i <= 30 or matched_count % 200 == 0:
                    print(f"  [{i}] {name[:45]} → {', '.join(sources[:3])}")

        if i % 500 == 0:
            print(f"  Processed {i}/{len(ingredients)}...")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total synthetic ingredients: {len(ingredients)}")
    print(f"Matched to images: {matched_count}")
    print(f"Match rate: {matched_count/len(ingredients)*100:.1f}%")

    # Save matches
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(matches, f, indent=2)

    print(f"\nMatches saved to: {OUTPUT_FILE}")

    # Show sample matches
    print("\nSample matches:")
    for m in matches[:15]:
        print(f"  {m['ingredient'][:50]}")
        print(f"    Sources: {', '.join(m['source_keywords'][:4])}")
        print(f"    Images: {len(m['all_images'])}")


if __name__ == '__main__':
    main()
