"""
Consolidate ingredient images from multiple locations into one master folder.

Sources:
- ~/Downloads/ingredient_images_1000x1000 (single images)
- ~/Downloads/ingredient_images_organized (subfolders with multiple images)
- ~/Downloads/Ingredients (subfolders)
- ~/Desktop/Ingredients (named images with prefixes)

Excludes:
- Generic AdobeStock images (no ingredient name)
- Screenshots (CleanShot)
- Non-image files
- Graphic design/infographic images
"""

import os
import re
import shutil
import hashlib
from pathlib import Path
from collections import defaultdict

# Source locations
SOURCES = [
    ('~/Downloads/ingredient_images_1000x1000', 'flat'),      # Flat folder with images
    ('~/Downloads/ingredient_images_organized', 'subfolders'), # Subfolders by ingredient
    ('~/Downloads/Ingredients', 'subfolders'),                 # Subfolders by ingredient
    ('~/Desktop/Ingredients', 'flat_prefixed'),               # Flat with hero-, field- prefixes
]

# Output location
OUTPUT_DIR = os.path.expanduser('~/Downloads/ingredient_images_master')

# Files to exclude (patterns)
EXCLUDE_PATTERNS = [
    r'^AdobeStock_\d+\.(jpeg|jpg|png)$',  # Generic AdobeStock without ingredient name
    r'^CleanShot',                          # Screenshots
    r'\.gif$',                              # GIFs
    r'iOS.*Template',                       # iOS templates
    r'\.xlsx?$',                            # Excel files
    r'\.txt$',                              # Text files
    r'\.svg$',                              # SVG files (keep only raster)
]

# Image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def should_exclude(filename):
    """Check if file should be excluded."""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            return True
    return False


def is_image(filename):
    """Check if file is an image."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in IMAGE_EXTENSIONS


def extract_ingredient_name(filename, source_type, parent_folder=None):
    """
    Extract ingredient name from filename or parent folder.

    Returns: ingredient_name or None
    """
    # If in subfolder, use folder name
    if source_type in ('subfolders',) and parent_folder:
        return parent_folder

    # For flat_prefixed (Desktop/Ingredients), extract from filename
    if source_type == 'flat_prefixed':
        # Pattern: prefix-ingredient_name_stockid.ext
        # e.g., hero-Acacia decurrens flower_280626044.png
        match = re.match(r'^(hero|field|drop|flowers|fruit|closeup|macro)-(.+?)(?:_\d+)?\.(jpg|jpeg|png)$',
                        filename, re.IGNORECASE)
        if match:
            return match.group(2).replace('-', ' ').replace('_', ' ').strip()

        # Also handle AdobeStock with ingredient name
        # e.g., "ingredient name-AdobeStock_123.jpeg"
        match = re.match(r'^(.+?)-AdobeStock_\d+\.(jpg|jpeg|png)$', filename, re.IGNORECASE)
        if match:
            return match.group(1).replace('-', ' ').replace('_', ' ').strip()

    # For flat folders (ingredient_images_1000x1000), use filename as ingredient
    if source_type == 'flat':
        # Remove extension and stock IDs
        name = os.path.splitext(filename)[0]
        # Remove trailing stock IDs like _123456789
        name = re.sub(r'[_-](?:AdobeStock_)?\d{6,}$', '', name)
        # Clean up
        name = name.replace('_', ' ').replace('-', ' ').strip()
        if len(name) > 3:  # Reasonable ingredient name
            return name

    return None


def get_file_hash(filepath, quick=True):
    """Get hash of file for duplicate detection."""
    if quick:
        # Quick hash: just file size + first 1KB
        size = os.path.getsize(filepath)
        with open(filepath, 'rb') as f:
            first_kb = f.read(1024)
        return f"{size}_{hashlib.md5(first_kb).hexdigest()[:8]}"
    else:
        # Full hash
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()


def scan_sources():
    """Scan all source locations and catalog images."""
    all_images = []  # List of (ingredient_name, filepath, filesize, image_type, source)
    source_counts = {}  # Track counts per source

    for source_path, source_type in SOURCES:
        source_path = os.path.expanduser(source_path)

        if not os.path.exists(source_path):
            print(f"  Skipping (not found): {source_path}")
            continue

        print(f"\nScanning: {source_path}")
        count = 0

        if source_type == 'flat':
            # Single folder with images
            for filename in os.listdir(source_path):
                filepath = os.path.join(source_path, filename)
                if not os.path.isfile(filepath):
                    continue
                if not is_image(filename):
                    continue
                if should_exclude(filename):
                    continue

                ingredient = extract_ingredient_name(filename, source_type)
                if ingredient:
                    filesize = os.path.getsize(filepath)
                    img_type = 'standard'
                    all_images.append((ingredient, filepath, filesize, img_type, source_path))
                    count += 1

        elif source_type == 'flat_prefixed':
            # Flat folder with prefixed filenames
            for filename in os.listdir(source_path):
                filepath = os.path.join(source_path, filename)
                if not os.path.isfile(filepath):
                    continue
                if not is_image(filename):
                    continue
                if should_exclude(filename):
                    continue

                ingredient = extract_ingredient_name(filename, source_type)
                if ingredient:
                    filesize = os.path.getsize(filepath)
                    # Detect image type from prefix
                    lower = filename.lower()
                    if lower.startswith('hero'):
                        img_type = 'hero'
                    elif lower.startswith('field'):
                        img_type = 'field'
                    elif lower.startswith(('drop', 'closeup', 'macro')):
                        img_type = 'closeup'
                    elif lower.startswith(('flowers', 'fruit', 'leaf')):
                        img_type = 'botanical'
                    else:
                        img_type = 'standard'
                    all_images.append((ingredient, filepath, filesize, img_type, source_path))
                    count += 1

        elif source_type == 'subfolders':
            # Subfolders by ingredient name
            for folder in os.listdir(source_path):
                folder_path = os.path.join(source_path, folder)
                if not os.path.isdir(folder_path):
                    continue
                if folder.startswith('.'):
                    continue

                # Folder name is ingredient name
                ingredient = folder

                for filename in os.listdir(folder_path):
                    filepath = os.path.join(folder_path, filename)
                    if not os.path.isfile(filepath):
                        continue
                    if not is_image(filename):
                        continue
                    if should_exclude(filename):
                        continue

                    filesize = os.path.getsize(filepath)
                    # Detect image type
                    lower = filename.lower()
                    if 'white' in lower or 'isolated' in lower:
                        img_type = 'hero'
                    elif 'field' in lower or 'branch' in lower or 'plant' in lower:
                        img_type = 'field'
                    else:
                        img_type = 'standard'
                    all_images.append((ingredient, filepath, filesize, img_type, source_path))
                    count += 1

        source_counts[source_path] = count
        print(f"  Found {count} images")

    print(f"\n--- SOURCE BREAKDOWN ---")
    for src, cnt in source_counts.items():
        print(f"  {src}: {cnt} images")

    return all_images


def find_duplicates(images):
    """Find duplicate images (same content, different sizes)."""
    # Group by ingredient name (normalized)
    by_ingredient = defaultdict(list)
    for img in images:
        ingredient = img[0]
        normalized = ingredient.lower().strip()
        by_ingredient[normalized].append(img)

    # Find duplicates within each ingredient
    duplicates = []
    unique = []

    for norm_name, img_list in by_ingredient.items():
        if len(img_list) == 1:
            unique.append(img_list[0])
            continue

        # Check for same-content duplicates (by quick hash)
        seen_hashes = {}
        for img in img_list:
            ingredient, filepath, filesize, img_type, source = img
            file_hash = get_file_hash(filepath)

            if file_hash in seen_hashes:
                # Duplicate - keep larger one
                existing = seen_hashes[file_hash]
                if filesize > existing[2]:
                    duplicates.append(existing)
                    seen_hashes[file_hash] = img
                else:
                    duplicates.append(img)
            else:
                seen_hashes[file_hash] = img

        unique.extend(seen_hashes.values())

    return unique, duplicates


def consolidate(images, output_dir, dry_run=True):
    """Copy images to consolidated folder."""
    os.makedirs(output_dir, exist_ok=True)

    # Group by ingredient
    by_ingredient = defaultdict(list)
    for img in images:
        ingredient, filepath, filesize, img_type, source = img
        by_ingredient[ingredient].append((filepath, filesize, img_type, source))

    print(f"\n{'='*50}")
    print(f"CONSOLIDATION {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*50}")
    print(f"Unique ingredients: {len(by_ingredient)}")
    print(f"Total images: {len(images)}")
    print(f"Output: {output_dir}")

    if dry_run:
        # Show sample with sources
        print(f"\nSample (first 15):")
        for i, (ingredient, imgs) in enumerate(list(by_ingredient.items())[:15]):
            print(f"  {ingredient}: {len(imgs)} image(s)")
            for filepath, filesize, img_type, source in imgs[:3]:
                short_source = source.replace(os.path.expanduser('~'), '~')
                print(f"    - {os.path.basename(filepath)} ({filesize//1024}KB, {img_type})")
                print(f"      from: {short_source}")

        print(f"\nTo consolidate, run with --consolidate")
        return

    # Actually copy files
    copied = 0
    for ingredient, imgs in by_ingredient.items():
        # Create ingredient folder
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', ingredient)
        ingredient_dir = os.path.join(output_dir, safe_name)
        os.makedirs(ingredient_dir, exist_ok=True)

        for filepath, filesize, img_type, source in imgs:
            src_filename = os.path.basename(filepath)
            # Prefix with image type if known
            if img_type != 'standard':
                dest_filename = f"{img_type}_{src_filename}"
            else:
                dest_filename = src_filename

            dest_path = os.path.join(ingredient_dir, dest_filename)

            # Handle duplicates
            counter = 1
            while os.path.exists(dest_path):
                name, ext = os.path.splitext(dest_filename)
                dest_path = os.path.join(ingredient_dir, f"{name}_{counter}{ext}")
                counter += 1

            shutil.copy2(filepath, dest_path)
            copied += 1

        if copied % 100 == 0:
            print(f"  Copied {copied} images...")

    print(f"\nCopied {copied} images to {output_dir}")


def main():
    import sys

    dry_run = '--consolidate' not in sys.argv

    print("="*50)
    print("INGREDIENT IMAGE CONSOLIDATOR")
    print("="*50)

    # Scan all sources
    print("\nScanning sources...")
    all_images = scan_sources()
    print(f"\nTotal images found: {len(all_images)}")

    # Find duplicates
    print("\nChecking for duplicates...")
    unique, duplicates = find_duplicates(all_images)
    print(f"Unique images: {len(unique)}")
    print(f"Duplicates (smaller sizes): {len(duplicates)}")

    if duplicates:
        print("\nSample duplicates:")
        for img in duplicates[:5]:
            print(f"  {img[0]}: {os.path.basename(img[1])} ({img[2]//1024}KB)")

    # Consolidate
    consolidate(unique, OUTPUT_DIR, dry_run=dry_run)

    if dry_run:
        print("\nTo actually consolidate, run:")
        print("  python3 consolidate_images.py --consolidate")


if __name__ == '__main__':
    main()
