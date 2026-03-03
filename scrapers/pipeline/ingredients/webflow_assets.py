#!/usr/bin/env python3
"""
Upload local images to Webflow's Asset CDN and update ingredients.
"""

import os
import re
import sqlite3
import requests
import time
from pathlib import Path
from typing import Optional, List, Tuple

# Load environment
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

DB_PATH = Path(__file__).parent.parent / "data" / "ingredients.db"
LOCAL_IMAGES_DIR = Path("/Users/jenmurphy/Downloads/ingredient_images_1000x1000")

WEBFLOW_API_BASE = "https://api.webflow.com/v2"
WEBFLOW_API_TOKEN = os.environ.get('WEBFLOW_API_TOKEN', '')
WEBFLOW_SITE_ID = os.environ.get('WEBFLOW_SITE_ID', '')


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


def get_ingredients_map() -> dict:
    """Get ingredients indexed by normalized name."""
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
    """Get local image files."""
    if not LOCAL_IMAGES_DIR.exists():
        return []
    images = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        images.extend(LOCAL_IMAGES_DIR.glob(ext))
    return sorted(images)


def match_images(ingredients: dict, images: List[Path]) -> List[Tuple[Path, dict]]:
    """Match images to ingredients."""
    matches = []

    for img_path in images:
        normalized = normalize_name(img_path.stem)

        # Exact match
        if normalized in ingredients:
            matches.append((img_path, ingredients[normalized]))
        else:
            # Partial match
            for norm_inci, ing in ingredients.items():
                if (normalized in norm_inci or norm_inci in normalized) and len(normalized) > 5:
                    matches.append((img_path, ing))
                    break

    return matches


def upload_to_webflow_assets(image_path: Path) -> Optional[str]:
    """
    Upload image to Webflow and return the hosted URL.
    Uses Webflow's asset upload API.
    """
    headers = {
        'Authorization': f'Bearer {WEBFLOW_API_TOKEN}',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }

    # Step 1: Request upload credentials from Webflow
    upload_request_url = f"{WEBFLOW_API_BASE}/sites/{WEBFLOW_SITE_ID}/assets"

    file_name = image_path.name
    # Create a unique hash based on file content
    import hashlib
    with open(image_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()

    try:
        # Request upload credentials
        response = requests.post(
            upload_request_url,
            headers=headers,
            json={
                'fileName': file_name,
                'fileHash': file_hash,
            },
            timeout=30
        )

        if response.status_code not in [200, 201, 202]:
            print(f"Upload request failed: {response.status_code} - {response.text[:200]}")
            return None

        upload_data = response.json()

        # Get the S3 upload URL and form fields
        upload_url = upload_data.get('uploadUrl')
        upload_details = upload_data.get('uploadDetails', {})
        hosted_url = upload_data.get('hostedUrl')

        if not upload_url or not upload_details:
            print(f"Missing upload URL or details")
            return None

        # Step 2: Upload file to S3
        with open(image_path, 'rb') as f:
            file_data = f.read()

        # Build form data - S3 requires Content-Type as BOTH a form field AND file content type
        # Order matters: fields first, then file last
        form_data = {
            'acl': upload_details['acl'],
            'bucket': upload_details['bucket'],
            'X-Amz-Algorithm': upload_details['X-Amz-Algorithm'],
            'X-Amz-Credential': upload_details['X-Amz-Credential'],
            'X-Amz-Date': upload_details['X-Amz-Date'],
            'key': upload_details['key'],
            'Policy': upload_details['Policy'],
            'X-Amz-Signature': upload_details['X-Amz-Signature'],
            'success_action_status': upload_details['success_action_status'],
            'Cache-Control': upload_details['Cache-Control'],
            'Content-Type': upload_details['content-type'],  # Required in form data!
        }

        files = {
            'file': (file_name, file_data, upload_details['content-type'])
        }

        s3_response = requests.post(
            upload_url,
            data=form_data,
            files=files,
            timeout=120
        )

        if s3_response.status_code not in [200, 201, 204]:
            print(f"S3 upload failed: {s3_response.status_code} - {s3_response.text[:100]}")
            return None

        # Return the hosted CDN URL
        return hosted_url

    except Exception as e:
        print(f"Upload error: {e}")
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


def process_adobe_images(limit: int = None, dry_run: bool = False, overwrite: bool = True):
    """
    Process Adobe images:
    1. Match to ingredients
    2. Upload to Webflow assets
    3. Update database
    """
    print("Loading ingredients and images...")
    ingredients = get_ingredients_map()
    images = get_local_images()

    print(f"Found {len(images)} local Adobe images")
    print(f"Found {len(ingredients)} ingredients in database")

    matches = match_images(ingredients, images)
    print(f"Matched {len(matches)} images to ingredients")

    if not overwrite:
        matches = [(img, ing) for img, ing in matches if not ing['has_image']]
        print(f"After skipping existing: {len(matches)} to process")

    if limit:
        matches = matches[:limit]

    if dry_run:
        print("\n=== DRY RUN ===")
        for img, ing in matches[:30]:
            status = "(has image)" if ing['has_image'] else "(no image)"
            print(f"  {img.name} -> {ing['inci_name']} {status}")
        if len(matches) > 30:
            print(f"  ... and {len(matches) - 30} more")
        return

    print(f"\nProcessing {len(matches)} images...")
    success = 0
    failed = 0

    for i, (img_path, ing_data) in enumerate(matches, 1):
        print(f"  [{i}/{len(matches)}] {img_path.name}...", end=" ", flush=True)

        url = upload_to_webflow_assets(img_path)

        if url:
            update_hero_image(ing_data['id'], url)
            print(f"OK -> {url[:50]}...")
            success += 1
        else:
            print("FAILED")
            failed += 1

        # Rate limiting
        time.sleep(0.5)

    print(f"\nDone! Success: {success}, Failed: {failed}")
    return success, failed


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv
    no_overwrite = "--no-overwrite" in sys.argv

    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=")[1])
            except:
                pass

    process_adobe_images(limit=limit, dry_run=dry_run, overwrite=not no_overwrite)
