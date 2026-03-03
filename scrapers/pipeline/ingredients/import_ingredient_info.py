"""
Import ingredient info from Excel files to Webflow.

Reads Q&A data from ~/Downloads/ingredient-info/ folders and updates
corresponding Webflow ingredient entries with:
- Scientific/common names, plant family, origin
- Form, plant part, how it's made
- Benefits, uses, functions
- Aromatherapy, scent profile
- Safety info, CAS/EC numbers
- Proper MLA citations

Matches ingredients by both INCI name and common name.
"""

import os
import re
import time
from pathlib import Path
from collections import defaultdict

import pandas as pd
import requests
from dotenv import load_dotenv

# Load environment
load_dotenv(Path.home() / 'Desktop/product-card-project/pipeline/.env')

API_TOKEN = os.environ.get('WEBFLOW_API_TOKEN', '')
COLLECTION_ID = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')
INFO_DIR = os.path.expanduser('~/Downloads/ingredient-info')

HEADERS = {
    'Authorization': f'Bearer {API_TOKEN}',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
}

# Junk patterns to filter out bad Webflow entries
JUNK_PATTERNS = [
    r'^\d+[-\s]*\d*[-\s]*\d*$',  # CAS numbers like "97-59-6"
    r'^[A-Z\s]{2,4}$',  # Short all-caps like "EXT", "3S"
    r'^also known as',  # Descriptions starting with "also known as"
    r'^●',  # Bullet point entries
    r'^\d+$',  # Pure numbers
    r'^[A-Z]\d+$',  # Like "C12", "B5"
    r'PHARMACEUTICAL',  # Pharmaceutical standards
    r'^USP$',
    r'^NF$',
]


def is_junk_entry(name):
    """Check if a Webflow entry name is junk (not a real ingredient)."""
    if not name:
        return True
    for pattern in JUNK_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return True
    # Also filter very short names
    if len(name) <= 3 and not re.match(r'^[A-Z][a-z]+$', name):
        return True
    return False

# Map Excel questions to Webflow field slugs
QUESTION_TO_FIELD = {
    "What is the ingredient's scientific name?": 'inci',
    "What is the ingredient's common name?": 'also-known-as',
    "What is the ingredient's plant family name?": 'plant-family',
    "Where is the ingredient's area of origin?": 'origin-2',
    "What is the form of the ingredient?": 'form-3',
    "What part of the plant is used?": 'plant-part',
    "How is the ingredient made?": 'how-it-s-made',
    "What are the ingredient's features & properties?": '_features',  # Added to what-it-is
    "What are the ingredient's benefits to humans?": '_benefits',  # Added to support-details
    "What are this ingredient's uses for humans?": 'medicine',
    "What are the ingredient's industrial & cosmetic uses?": '_industrial_uses',
    "What are the cosmetic functions in products?": 'functions-3',
    "What is the chemistry/chemical structure?": '_chemistry',
    "How is it used in aromatherapy?": 'aromatherapy',
    "What are its aromatherapeutic properties?": '_aroma_props',  # Combined with aromatherapy
    "What is its scent profile?": 'scent',
    "What is the safety recommendation?": '_safety_rec',
    "What is the safety rating?": '_safety_rating',
    "What are the safety concerns?": '_safety_concerns',
    "What are the contraindications of use?": '_contraindications',
    "What is the CAS number?": 'cas-2',
    "What is the EC number?": 'ec-2',
}


def normalize_name(name):
    """Normalize ingredient name for matching."""
    if not name:
        return ''
    # Remove common suffixes, brackets, asterisks
    name = re.sub(r'\s*\*+$', '', name)  # Trailing asterisks
    name = re.sub(r'\s*\[.*?\]', '', name)  # Bracketed common names
    name = re.sub(r'\s*\(.*?\)', '', name)  # Parenthetical names
    name = re.sub(r'\s*／.*$', '', name)  # Slash alternatives
    name = re.sub(r',\s*$', '', name)  # Trailing commas
    return name.strip().lower()


def extract_base_botanical(name):
    """Extract base botanical name (genus + species) for matching."""
    normalized = normalize_name(name)
    # Match common botanical pattern: "genus species" at start
    match = re.match(r'^([a-z]+\s+[a-z]+)', normalized)
    if match:
        return match.group(1)
    return normalized


def get_all_webflow_items():
    """Fetch all ingredient items from Webflow."""
    items = []
    offset = 0
    limit = 100

    while True:
        resp = requests.get(
            f'https://api.webflow.com/v2/collections/{COLLECTION_ID}/items',
            headers=HEADERS,
            params={'offset': offset, 'limit': limit}
        )
        if not resp.ok:
            print(f"Error fetching items: {resp.status_code}")
            break

        data = resp.json()
        batch = data.get('items', [])
        items.extend(batch)

        if len(batch) < limit:
            break
        offset += limit
        time.sleep(0.2)

    return items


def build_name_indices(items):
    """Build indices for matching by various name forms."""
    exact_index = {}  # Exact normalized name -> item
    nospace_index = {}  # Name without spaces -> item (for minor variations)
    contains_index = defaultdict(list)  # Substring -> items
    botanical_index = defaultdict(list)  # Base botanical -> items
    skipped_junk = 0

    for item in items:
        name = item.get('fieldData', {}).get('name', '')
        slug = item.get('fieldData', {}).get('slug', '')
        item_id = item.get('id', '')

        if not name:
            continue

        # Skip junk entries
        if is_junk_entry(name):
            skipped_junk += 1
            continue

        # Exact match index (by name only, not slug - slugs can be misleading)
        normalized = normalize_name(name)
        exact_index[normalized] = item

        # No-space index for matching variations like "Aminomethylpropanediol" vs "Aminomethyl Propanediol"
        nospace = normalized.replace(' ', '')
        nospace_index[nospace] = item

        # Botanical base index
        base = extract_base_botanical(name)
        if len(base) > 5:
            botanical_index[base].append(item)

        # Contains index (for partial matching)
        words = normalized.split()
        for i in range(len(words)):
            for j in range(i + 1, min(i + 4, len(words) + 1)):
                phrase = ' '.join(words[i:j])
                if len(phrase) > 4:
                    contains_index[phrase].append(item)

    print(f"  Indexed {len(exact_index)} items (skipped {skipped_junk} junk entries)")
    return exact_index, nospace_index, contains_index, botanical_index


def similarity_score(s1, s2):
    """Calculate similarity between two strings (0-1)."""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def find_matching_item(folder_name, exact_index, nospace_index, contains_index, botanical_index, all_items):
    """Find the best matching Webflow item for an ingredient folder."""
    # Normalize folder name
    normalized = normalize_name(folder_name)
    nospace = normalized.replace(' ', '')

    # 1. Exact match (highest priority)
    if normalized in exact_index:
        item = exact_index[normalized]
        if not is_junk_entry(item.get('fieldData', {}).get('name', '')):
            return item, 'exact'

    # 2. No-space match (for variations like "Aminomethylpropanediol" vs "Aminomethyl Propanediol")
    if nospace in nospace_index:
        item = nospace_index[nospace]
        if not is_junk_entry(item.get('fieldData', {}).get('name', '')):
            return item, 'nospace-exact'

    # 3. Very high similarity match (>0.95 to avoid false positives like Arachidic/Arachidonic)
    best_match = None
    best_score = 0
    for item in all_items:
        name = item.get('fieldData', {}).get('name', '')
        if is_junk_entry(name):
            continue
        score = similarity_score(folder_name, name)
        if score > best_score and score > 0.95:
            best_score = score
            best_match = item

    if best_match:
        return best_match, f'similarity:{best_score:.2f}'

    # 4. Try base botanical name (for exact botanical matches only)
    base = extract_base_botanical(folder_name)
    if base in botanical_index:
        valid = [i for i in botanical_index[base]
                 if not is_junk_entry(i.get('fieldData', {}).get('name', ''))]
        # Only use if there's exactly one match or one is very similar
        if len(valid) == 1:
            return valid[0], 'botanical'
        # Check for high similarity among botanical matches
        for item in valid:
            item_name = item.get('fieldData', {}).get('name', '')
            score = similarity_score(folder_name, item_name)
            if score > 0.85:
                return item, f'botanical+similarity:{score:.2f}'

    # Skip loose "contains" matching to avoid imprecise matches
    return None, None


def read_ingredient_info(folder_path):
    """Read all Excel files in an ingredient folder and combine data."""
    info = {}
    citations = []

    for file in os.listdir(folder_path):
        if not file.endswith('.xlsx'):
            continue

        try:
            df = pd.read_excel(os.path.join(folder_path, file))

            for _, row in df.iterrows():
                question = row.get('Question', '')
                answer = row.get('Answer', '')
                citation = row.get('Citation', '')

                if pd.isna(question) or pd.isna(answer):
                    continue

                question = str(question).strip()
                answer = str(answer).strip()

                if question in QUESTION_TO_FIELD:
                    field = QUESTION_TO_FIELD[question]
                    # Store answer and citation
                    if answer and answer.lower() not in ('not applicable', 'not used', 'none known', 'none'):
                        info[field] = answer
                        if pd.notna(citation) and str(citation).strip():
                            citations.append({
                                'field': field,
                                'question': question,
                                'source': str(citation).strip()
                            })

        except Exception as e:
            print(f"  Error reading {file}: {e}")

    return info, citations


def format_citations_mla(citations):
    """Format citations in MLA style for Webflow rich text field."""
    if not citations:
        return ''

    # Group by source URL
    sources = {}
    for c in citations:
        url = c.get('source', '')
        if url:
            if url not in sources:
                sources[url] = []
            sources[url].append(c.get('question', ''))

    if not sources:
        return ''

    # Format as rich text HTML
    lines = ['<h4>Sources & References</h4>', '<ul>']
    for url, questions in sources.items():
        # Extract domain for citation
        domain = re.search(r'https?://(?:www\.)?([^/]+)', url)
        domain_name = domain.group(1) if domain else url

        # Format as MLA-style web citation
        lines.append(f'<li><a href="{url}" target="_blank">{domain_name}</a></li>')

    lines.append('</ul>')
    return '\n'.join(lines)


def build_update_payload(info, citations, existing_data):
    """Build the Webflow update payload from extracted info."""
    field_data = {}

    # Direct field mappings
    direct_fields = [
        'inci', 'also-known-as', 'plant-family', 'origin-2', 'form-3',
        'plant-part', 'how-it-s-made', 'medicine', 'functions-3',
        'aromatherapy', 'scent', 'cas-2', 'ec-2'
    ]

    for field in direct_fields:
        if field in info:
            value = info[field]
            # For RichText fields, wrap in paragraph
            if field in ('inci', 'also-known-as', 'plant-family', 'how-it-s-made',
                        'medicine', 'aromatherapy', 'scent'):
                value = f'<p>{value}</p>'
            field_data[field] = value

    # Combine aromatherapy fields
    if '_aroma_props' in info and 'aromatherapy' in field_data:
        existing = field_data['aromatherapy'].replace('</p>', '')
        field_data['aromatherapy'] = f'{existing}</p><p><strong>Properties:</strong> {info["_aroma_props"]}</p>'

    # Combine safety fields into safety-ratings-contraindications-2
    safety_parts = []
    if '_safety_rating' in info:
        safety_parts.append(f"Rating: {info['_safety_rating']}")
    if '_safety_rec' in info:
        safety_parts.append(f"Recommendation: {info['_safety_rec']}")
    if '_safety_concerns' in info:
        safety_parts.append(f"Concerns: {info['_safety_concerns']}")
    if '_contraindications' in info:
        safety_parts.append(f"Contraindications: {info['_contraindications']}")

    if safety_parts:
        field_data['safety-ratings-contraindications-2'] = ' | '.join(safety_parts)

    # Build support-details from benefits
    if '_benefits' in info:
        field_data['support-details'] = info['_benefits']

    # Add citations to references field
    citations_html = format_citations_mla(citations)
    if citations_html:
        field_data['how-we-know-references-mla-citations'] = citations_html

    return field_data


def update_webflow_item(item_id, field_data, dry_run=True):
    """Update a Webflow item with new field data."""
    if dry_run:
        return True

    resp = requests.patch(
        f'https://api.webflow.com/v2/collections/{COLLECTION_ID}/items/{item_id}',
        headers=HEADERS,
        json={'fieldData': field_data}
    )

    if not resp.ok:
        print(f"    Error updating: {resp.status_code} - {resp.text[:200]}")
        return False

    return True


def main():
    import sys

    dry_run = '--update' not in sys.argv
    limit = None
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    print("=" * 60)
    print("INGREDIENT INFO IMPORTER")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print(f"Info source: {INFO_DIR}")
    print()

    # Get all Webflow items
    print("Fetching Webflow ingredients...")
    items = get_all_webflow_items()
    print(f"Found {len(items)} Webflow ingredients")

    # Build indices
    print("Building name indices...")
    exact_index, nospace_index, contains_index, botanical_index = build_name_indices(items)

    # Scan info folders
    print(f"\nScanning info folders...")
    folders = [f for f in os.listdir(INFO_DIR)
               if os.path.isdir(os.path.join(INFO_DIR, f)) and not f.startswith('.')]
    print(f"Found {len(folders)} ingredient info folders")

    # Process each folder
    matched = 0
    unmatched = 0
    updated = 0
    skipped = 0

    unmatched_list = []

    for i, folder in enumerate(sorted(folders)):
        if limit and i >= limit:
            break

        folder_path = os.path.join(INFO_DIR, folder)

        # Find matching Webflow item
        item, match_type = find_matching_item(folder, exact_index, nospace_index, contains_index, botanical_index, items)

        if not item:
            unmatched += 1
            unmatched_list.append(folder)
            continue

        matched += 1
        item_name = item.get('fieldData', {}).get('name', '')
        item_id = item.get('id', '')

        # Read info from Excel files
        info, citations = read_ingredient_info(folder_path)

        if not info:
            skipped += 1
            continue

        # Build update payload
        field_data = build_update_payload(info, citations, item.get('fieldData', {}))

        if not field_data:
            skipped += 1
            continue

        # Update or show preview
        if dry_run:
            print(f"\n{folder} -> {item_name} [{match_type}]")
            print(f"  Fields to update: {list(field_data.keys())}")
            if citations:
                print(f"  Citations: {len(set(c['source'] for c in citations))} sources")
        else:
            print(f"Updating: {item_name}...", end=' ')
            success = update_webflow_item(item_id, field_data, dry_run=False)
            if success:
                updated += 1
                print("OK")
            else:
                print("FAILED")
            time.sleep(0.3)  # Rate limiting

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Info folders:     {len(folders)}")
    print(f"Matched:          {matched}")
    print(f"Unmatched:        {unmatched}")
    print(f"Skipped (empty):  {skipped}")
    if not dry_run:
        print(f"Updated:          {updated}")

    if unmatched_list and unmatched <= 30:
        print(f"\nUnmatched folders:")
        for f in unmatched_list[:30]:
            print(f"  - {f}")

    if dry_run:
        print(f"\nTo apply updates, run with --update")
        print(f"  python3 import_ingredient_info.py --update")
        print(f"\nTo test with a limit:")
        print(f"  python3 import_ingredient_info.py --update --limit=5")


if __name__ == '__main__':
    main()
