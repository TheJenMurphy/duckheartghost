#!/usr/bin/env python3
"""
Match local ingredient images to database entries and upload to Google Drive.
Images in Downloads/ingredient_images_1000x1000/ are named by INCI name.
"""

import sqlite3
import subprocess
import os
import re
from pathlib import Path
from typing import Optional, List, Tuple

DB_PATH = Path(__file__).parent.parent / "data" / "ingredients.db"
LOCAL_IMAGES_DIR = Path("/Users/jenmurphy/Downloads/ingredient_images_1000x1000")
GDRIVE_FOLDER = "Ingredient Images"  # Will be created in Google Drive


def normalize_name(name: str) -> str:
    """Normalize ingredient name for matching."""
    if not name:
        return ""
    # Remove file extension
    name = re.sub(r'\.(jpg|jpeg|png|gif)$', '', name, flags=re.IGNORECASE)
    # Normalize to lowercase, remove extra spaces
    name = name.lower().strip()
    # Replace underscores and hyphens with spaces
    name = re.sub(r'[_-]', ' ', name)
    # Remove parenthetical common names for matching
    # e.g., "Rosa Damascena (Bulgarian Rose)" -> "rosa damascena"
    name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def get_all_ingredients() -> dict:
    """Get all ingredients from database, indexed by normalized INCI name."""
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
    """Get all image files from the local images directory."""
    if not LOCAL_IMAGES_DIR.exists():
        print(f"Images directory not found: {LOCAL_IMAGES_DIR}")
        return []

    images = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif']:
        images.extend(LOCAL_IMAGES_DIR.glob(ext))

    return sorted(images)


def match_images_to_ingredients() -> List[Tuple[Path, dict]]:
    """Match local images to ingredients in the database."""
    ingredients = get_all_ingredients()
    images = get_local_images()

    matches = []
    unmatched = []

    for img_path in images:
        # Get filename without extension
        img_name = img_path.stem
        normalized = normalize_name(img_name)

        if normalized in ingredients:
            matches.append((img_path, ingredients[normalized]))
        else:
            # Try partial matching
            found = False
            for norm_inci, ing_data in ingredients.items():
                # Check if image name is contained in INCI name or vice versa
                if normalized in norm_inci or norm_inci in normalized:
                    matches.append((img_path, ing_data))
                    found = True
                    break
            if not found:
                unmatched.append(img_path)

    return matches, unmatched


def upload_to_gdrive(local_path: Path, remote_folder: str) -> Optional[str]:
    """
    Upload a file to Google Drive and return the shareable URL.
    Uses rclone which should already be configured.
    """
    remote_path = f"gdrive:{remote_folder}/{local_path.name}"

    try:
        # Upload the file
        result = subprocess.run(
            ['rclone', 'copy', str(local_path), f"gdrive:{remote_folder}/"],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            print(f"Upload failed for {local_path.name}: {result.stderr}")
            return None

        # Get shareable link
        result = subprocess.run(
            ['rclone', 'link', remote_path],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            url = result.stdout.strip()
            # Convert Google Drive link to direct image URL
            # From: https://drive.google.com/file/d/FILE_ID/view?usp=sharing
            # To: https://drive.google.com/uc?export=view&id=FILE_ID
            if 'drive.google.com' in url:
                import re
                match = re.search(r'/d/([^/]+)/', url)
                if match:
                    file_id = match.group(1)
                    url = f"https://drive.google.com/uc?export=view&id={file_id}"
            return url
        else:
            print(f"Failed to get link for {local_path.name}: {result.stderr}")
            return None

    except subprocess.TimeoutExpired:
        print(f"Timeout uploading {local_path.name}")
        return None
    except Exception as e:
        print(f"Error uploading {local_path.name}: {e}")
        return None


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


def process_local_images(dry_run: bool = False, skip_existing: bool = True, limit: int = None):
    """
    Main function to process local images:
    1. Match images to ingredients
    2. Upload to Google Drive
    3. Update database with URLs

    Args:
        dry_run: If True, just report matches without uploading
        skip_existing: Skip ingredients that already have hero images
        limit: Maximum number of images to process
    """
    print("Matching local images to ingredients...")
    matches, unmatched = match_images_to_ingredients()

    print(f"Found {len(matches)} matches, {len(unmatched)} unmatched images")

    if skip_existing:
        matches = [(img, ing) for img, ing in matches if not ing['has_image']]
        print(f"After skipping existing: {len(matches)} to process")

    if limit:
        matches = matches[:limit]

    if dry_run:
        print("\n=== DRY RUN - Would process: ===")
        for img_path, ing_data in matches[:20]:
            print(f"  {img_path.name} -> {ing_data['inci_name']}")
        if len(matches) > 20:
            print(f"  ... and {len(matches) - 20} more")
        return

    print(f"\nUploading {len(matches)} images to Google Drive...")

    success = 0
    failed = 0

    for i, (img_path, ing_data) in enumerate(matches, 1):
        print(f"  [{i}/{len(matches)}] {img_path.name}...", end=" ", flush=True)

        url = upload_to_gdrive(img_path, GDRIVE_FOLDER)

        if url:
            update_hero_image(ing_data['id'], url)
            print("OK")
            success += 1
        else:
            print("FAILED")
            failed += 1

    print(f"\nDone! Success: {success}, Failed: {failed}")
    return success, failed


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv
    no_skip = "--no-skip" in sys.argv

    # Check for limit argument
    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=")[1])
            except ValueError:
                pass

    process_local_images(dry_run=dry_run, skip_existing=not no_skip, limit=limit)
