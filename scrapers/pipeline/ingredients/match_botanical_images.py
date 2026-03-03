#!/usr/bin/env python3
"""
Match botanical/plant-derived ingredients to plant images.

This script:
1. Loads plant-derived ingredients from Webflow that don't have gallery images
2. Matches ingredient names to image folders using botanical names
3. Outputs matches for syncing to Webflow

Usage:
    python match_botanical_images.py
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
OUTPUT_FILE = PROJECT_DIR / "botanical_image_matches.json"

# Image folders
GDRIVE_MASTER_PATH = Path("/Users/jenmurphy/Library/CloudStorage/GoogleDrive-hello@iheartclean.beauty/My Drive/Ingredient Images/master")

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


def extract_botanical_names(ingredient_name: str) -> List[str]:
    """Extract botanical and common names from ingredient name."""
    names = []

    # Pattern: "Scientific Name (Common Name) Part"
    # e.g., "Zingiber Officinale (Ginger) Root Extract"
    match = re.match(r'^([A-Z][a-z]+\s+[A-Za-z]+)\s*\(([^)]+)\)', ingredient_name)
    if match:
        scientific = match.group(1).strip()
        common = match.group(2).strip()
        names.append(scientific)
        names.append(common)
        # Also add genus only
        genus = scientific.split()[0]
        if len(genus) > 3:
            names.append(genus)
    else:
        # Try to extract just scientific name
        match = re.match(r'^([A-Z][a-z]+\s+[A-Za-z]+)', ingredient_name)
        if match:
            scientific = match.group(1).strip()
            names.append(scientific)
            genus = scientific.split()[0]
            if len(genus) > 3:
                names.append(genus)

    # Also extract any parenthetical common names
    parens = re.findall(r'\(([^)]+)\)', ingredient_name)
    for p in parens:
        if len(p) > 2:
            names.append(p.strip())

    # Add full name normalized
    names.append(ingredient_name)

    return [n for n in names if n]


def load_image_folders() -> Dict[str, Path]:
    """Load available image folders and their paths."""
    folders = {}

    if not GDRIVE_MASTER_PATH.exists():
        print(f"Warning: Image folder not found: {GDRIVE_MASTER_PATH}")
        return folders

    for folder in GDRIVE_MASTER_PATH.iterdir():
        if folder.is_dir():
            # Store by normalized name
            norm_name = normalize_name(folder.name)
            folders[norm_name] = folder

            # Also store by key parts
            for part in norm_name.split():
                if len(part) > 4:
                    if part not in folders:
                        folders[part] = folder

    return folders


def find_matching_folders(ingredient_name: str, all_folders: Dict[str, Path]) -> List[Path]:
    """Find image folders that match an ingredient name."""
    matches = []
    seen_paths = set()

    # Extract botanical names
    names = extract_botanical_names(ingredient_name)

    for name in names:
        norm_name = normalize_name(name)

        # Direct match
        if norm_name in all_folders:
            path = all_folders[norm_name]
            if path not in seen_paths:
                matches.append(path)
                seen_paths.add(path)

        # Partial match
        for folder_name, folder_path in all_folders.items():
            if folder_path in seen_paths:
                continue

            # Check if ingredient name is in folder name or vice versa
            if norm_name in folder_name or folder_name in norm_name:
                if folder_path not in seen_paths:
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

        # Natural score (higher = more natural)
        natural_score = 0
        for kw in NATURAL_IMAGE_KEYWORDS:
            if kw in fname:
                natural_score += 1

        # Studio score (higher = more studio-like, which we want to avoid)
        studio_score = 0
        for kw in STUDIO_IMAGE_KEYWORDS:
            if kw in fname:
                studio_score += 1

        # Prefer JPEGs (usually photos) over PNGs (often graphics)
        ext_score = 0 if ext in ['.jpg', '.jpeg'] else 1

        # Combined score: natural - studio, then by extension, then alphabetically
        return (-natural_score + studio_score, ext_score, fname)

    all_images.sort(key=score_image)
    return all_images[:10]  # Return top 10


def load_webflow_ingredients():
    """Load plant-derived ingredients without gallery images from Webflow."""
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

    # Filter to plant-derived without gallery images
    type_field = 'type-i-e-mineral-vitamin-botanical-synthetic-plant-derived-synthetic'
    filtered = []

    for item in items:
        fd = item.get('fieldData', {})
        ingredient_type = fd.get(type_field, '')

        # Only plant-derived
        if ingredient_type != 'plant-derived':
            continue

        # Skip if already has gallery images
        if fd.get('in-the-field-image', {}).get('url'):
            continue

        filtered.append({
            'id': item.get('id'),
            'name': fd.get('name', ''),
            'slug': fd.get('slug', '')
        })

    print(f"  Found {len(filtered)} plant-derived ingredients without gallery images")
    return filtered


def main():
    print("=" * 70)
    print("BOTANICAL INGREDIENT IMAGE MATCHER")
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

        # Find matching folders
        folders = find_matching_folders(name, all_folders)

        if folders:
            # Get images from folders
            images = get_images_from_folders(folders)

            if images:
                matched_count += 1
                matches.append({
                    'id': ing['id'],
                    'ingredient': name,
                    'slug': ing['slug'],
                    'matched_folders': [f.name for f in folders[:5]],
                    'all_images': images
                })

                if i <= 20 or i % 200 == 0:
                    print(f"  [{i}] {name[:45]} → {len(images)} images")

        if i % 500 == 0:
            print(f"  Processed {i}/{len(ingredients)}...")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total plant-derived ingredients: {len(ingredients)}")
    print(f"Matched to images: {matched_count}")
    print(f"Match rate: {matched_count/len(ingredients)*100:.1f}%")

    # Save matches
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(matches, f, indent=2)

    print(f"\nMatches saved to: {OUTPUT_FILE}")

    # Show sample matches
    print("\nSample matches:")
    for m in matches[:10]:
        print(f"  {m['ingredient'][:50]}")
        print(f"    Folders: {', '.join(m['matched_folders'][:3])}")
        print(f"    Images: {len(m['all_images'])}")


if __name__ == '__main__':
    main()
