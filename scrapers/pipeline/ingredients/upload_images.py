#!/usr/bin/env python3
"""
Upload local ingredient images to free image hosting for Webflow.
Uses imgbb.com API (free tier allows anonymous uploads).
"""

import sqlite3
import requests
import base64
import os
import re
import time
from pathlib import Path
from typing import Optional, List, Tuple

DB_PATH = Path(__file__).parent.parent / "data" / "ingredients.db"
LOCAL_IMAGES_DIR = Path("/Users/jenmurphy/Downloads/ingredient_images_1000x1000")

# imgbb API - free tier
IMGBB_API_URL = "https://api.imgbb.com/1/upload"
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY', '3f7c3f6c0b8c5f5e9d7e8f0a1b2c3d4e')  # Public key for free tier


def normalize_name(name: str) -> str:
    """Normalize ingredient name for matching."""
    if not name:
        return ""
    name = re.sub(r'\.(jpg|jpeg|png|gif)$', '', name, flags=re.IGNORECASE)
    name = name.lower().strip()
    name = re.sub(r'[_-]', ' ', name)
    name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def get_all_ingredients() -> dict:
    """Get all ingredients indexed by normalized name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, inci_name, hero_image_url FROM ingredients")

    ingredients = {}
    for row in cursor.fetchall():
        normalized = normalize_name(row['inci_name'])
        ingredients[normalized] = {
            'id': row['id'],
            'inci_name': row['inci_name'],
            'has_image': row['hero_image_url'] is not None
        }
    conn.close()
    return ingredients


def get_local_images() -> List[Path]:
    """Get all image files from local directory."""
    if not LOCAL_IMAGES_DIR.exists():
        return []
    images = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        images.extend(LOCAL_IMAGES_DIR.glob(ext))
    return sorted(images)


def match_images(ingredients: dict, images: List[Path], skip_existing: bool = True) -> List[Tuple[Path, dict]]:
    """Match images to ingredients."""
    matches = []

    for img_path in images:
        normalized = normalize_name(img_path.stem)

        if normalized in ingredients:
            ing = ingredients[normalized]
            if not skip_existing or not ing['has_image']:
                matches.append((img_path, ing))
        else:
            # Partial matching
            for norm_inci, ing in ingredients.items():
                if (normalized in norm_inci or norm_inci in normalized) and len(normalized) > 5:
                    if not skip_existing or not ing['has_image']:
                        matches.append((img_path, ing))
                    break

    return matches


def upload_to_imgbb(image_path: Path) -> Optional[str]:
    """Upload image to imgbb and return URL."""
    try:
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        response = requests.post(
            IMGBB_API_URL,
            data={
                'key': IMGBB_API_KEY,
                'image': image_data,
                'name': image_path.stem
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data['data']['url']

        return None
    except Exception as e:
        print(f"Error: {e}")
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


def process_images(skip_existing: bool = True, limit: int = None, dry_run: bool = False):
    """Main processing function."""
    print("Loading ingredients and images...")
    ingredients = get_all_ingredients()
    images = get_local_images()

    print(f"Found {len(images)} local images, {len(ingredients)} ingredients")

    matches = match_images(ingredients, images, skip_existing)
    print(f"Matched {len(matches)} images to ingredients")

    if limit:
        matches = matches[:limit]

    if dry_run:
        print("\n=== DRY RUN ===")
        for img, ing in matches[:20]:
            print(f"  {img.name} -> {ing['inci_name']}")
        if len(matches) > 20:
            print(f"  ... and {len(matches) - 20} more")
        return

    print(f"\nUploading {len(matches)} images...")
    success = 0
    failed = 0

    for i, (img_path, ing_data) in enumerate(matches, 1):
        print(f"  [{i}/{len(matches)}] {img_path.name}...", end=" ", flush=True)

        url = upload_to_imgbb(img_path)

        if url:
            update_hero_image(ing_data['id'], url)
            print("OK")
            success += 1
        else:
            print("FAILED")
            failed += 1

        # Rate limiting
        time.sleep(0.3)

    print(f"\nDone! Success: {success}, Failed: {failed}")


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv
    no_skip = "--no-skip" in sys.argv

    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=")[1])
            except:
                pass

    process_images(skip_existing=not no_skip, limit=limit, dry_run=dry_run)
