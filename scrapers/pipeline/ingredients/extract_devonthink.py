"""
Extract ingredient data from DevonThink database and update Webflow.

Processes:
- HTML files (web clips from EWG, PubChem, Wikipedia, etc.)
- PDF files (supplier specs, research papers)

Extracts:
- Safety ratings and concerns
- Chemical properties (CAS, molecular formula)
- Benefits and uses
- Origin and source information
"""

import os
import sys
import re
import time
import json
from pathlib import Path
from collections import defaultdict
from difflib import SequenceMatcher

# HTML parsing
from bs4 import BeautifulSoup

# PDF parsing
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

import requests

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Paths
DEVONTHINK_DB = os.path.expanduser('~/Databases/Ingredients.dtBase2/Files.noindex')
WEBFLOW_API_BASE = "https://api.webflow.com/v2"

# Patterns to extract ingredient names from filenames
INGREDIENT_PATTERNS = [
    r'^(.+?)\s*[-–]\s*(EWG|PubChem|Wikipedia|Cosmetics Info|COSING)',
    r'^(.+?)\s*\|\s*',
    r'^(.+?)\s*--\s*',
    r'^EWG Skin Deep.*What is (.+?)\.pdf$',
    r'^(.+?)\s*-\s*Cosmetics Info\.pdf$',
    r'^(.+?)\s*CID\s*\d+',
]


def extract_ingredient_from_filename(filename):
    """Extract ingredient name from document filename."""
    # Remove extension
    name = os.path.splitext(filename)[0]

    # Try patterns
    for pattern in INGREDIENT_PATTERNS:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Fallback: use filename if it looks like an ingredient name
    # (starts with capital, contains spaces or hyphens)
    if re.match(r'^[A-Z][a-z]+[\s\-]', name):
        # Clean up common suffixes
        name = re.sub(r'\s*[-–]\s*[A-Za-z]+\.[a-z]+$', '', name)
        name = re.sub(r'\s*\(\d+\)$', '', name)
        return name.strip()

    return None


def normalize_ingredient_name(name):
    """Normalize ingredient name for matching."""
    if not name:
        return ''
    name = name.lower().strip()
    name = re.sub(r'\s*\([^)]*\)', '', name)  # Remove parentheticals
    name = re.sub(r'\s*\[[^\]]*\]', '', name)  # Remove brackets
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def extract_text_from_html(filepath):
    """Extract text content from HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')

        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer']):
            element.decompose()

        text = soup.get_text(separator='\n')
        # Clean up
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)
    except Exception as e:
        return ''


def extract_text_from_pdf(filepath):
    """Extract text content from PDF file."""
    if not HAS_PDFPLUMBER:
        return ''

    try:
        text_parts = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages[:10]:  # Limit to first 10 pages
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return '\n'.join(text_parts)
    except Exception as e:
        return ''


def extract_ewg_data(text, filename):
    """Extract EWG Skin Deep data."""
    data = {}

    # Safety score (1-10)
    score_match = re.search(r'(?:hazard|score|rating)[:\s]*(\d+)', text, re.IGNORECASE)
    if score_match:
        data['ewg_score'] = int(score_match.group(1))

    # Concerns
    concerns = []
    concern_patterns = [
        r'concerns?[:\s]*([^\n]+)',
        r'(?:may cause|linked to|associated with)[:\s]*([^\n]+)',
    ]
    for pattern in concern_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        concerns.extend(matches)
    if concerns:
        data['safety_concerns'] = '; '.join(set(concerns))[:500]

    # Data availability
    if 'limited' in text.lower():
        data['data_note'] = 'Limited data available'

    data['source'] = 'EWG Skin Deep'
    data['source_url'] = 'https://www.ewg.org/skindeep/'

    return data


def extract_pubchem_data(text, filename):
    """Extract PubChem chemical data."""
    data = {}

    # CAS number
    cas_match = re.search(r'CAS[:\s#]*(\d{2,7}-\d{2}-\d)', text)
    if cas_match:
        data['cas_number'] = cas_match.group(1)

    # Molecular formula
    formula_match = re.search(r'(?:molecular formula|formula)[:\s]*([A-Z][A-Za-z0-9]+)', text, re.IGNORECASE)
    if formula_match:
        data['molecular_formula'] = formula_match.group(1)

    # Molecular weight
    weight_match = re.search(r'(?:molecular weight|molar mass)[:\s]*([\d.]+)\s*(?:g/mol)?', text, re.IGNORECASE)
    if weight_match:
        data['molecular_weight'] = weight_match.group(1)

    # Description
    desc_match = re.search(r'(?:description|appearance)[:\s]*([^\n]+)', text, re.IGNORECASE)
    if desc_match:
        data['appearance'] = desc_match.group(1)[:200]

    data['source'] = 'PubChem'
    data['source_url'] = 'https://pubchem.ncbi.nlm.nih.gov/'

    return data


def extract_cosing_data(text, filename):
    """Extract EU COSING database data."""
    data = {}

    # INCI name
    inci_match = re.search(r'INCI[:\s]*([^\n]+)', text, re.IGNORECASE)
    if inci_match:
        data['inci_name'] = inci_match.group(1).strip()

    # Functions
    func_match = re.search(r'(?:function|functions)[:\s]*([^\n]+)', text, re.IGNORECASE)
    if func_match:
        data['cosmetic_functions'] = func_match.group(1).strip()

    # Restrictions
    restrict_match = re.search(r'(?:restriction|restricted)[:\s]*([^\n]+)', text, re.IGNORECASE)
    if restrict_match:
        data['restrictions'] = restrict_match.group(1).strip()

    data['source'] = 'EU COSING'
    data['source_url'] = 'https://ec.europa.eu/growth/tools-databases/cosing/'

    return data


def extract_general_data(text, filename):
    """Extract general ingredient data from any document."""
    data = {}

    # Benefits
    benefit_patterns = [
        r'(?:benefits?|properties)[:\s]*([^\n]+)',
        r'(?:helps?|provides?|promotes?)[:\s]*([^\n]+)',
        r'(?:anti-?aging|moisturiz|hydrat|sooth|heal)[^\n]*',
    ]
    benefits = []
    for pattern in benefit_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        benefits.extend([m for m in matches if len(m) > 10])
    if benefits:
        data['benefits'] = '; '.join(set(benefits[:5]))[:500]

    # Uses
    use_patterns = [
        r'(?:uses?|applications?|used in)[:\s]*([^\n]+)',
    ]
    uses = []
    for pattern in use_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        uses.extend(matches)
    if uses:
        data['uses'] = '; '.join(set(uses[:3]))[:300]

    # Origin
    origin_match = re.search(r'(?:origin|derived from|sourced from|found in)[:\s]*([^\n]+)', text, re.IGNORECASE)
    if origin_match:
        data['origin'] = origin_match.group(1)[:200]

    # CAS if not already found
    if 'cas_number' not in data:
        cas_match = re.search(r'CAS[:\s#]*(\d{2,7}-\d{2}-\d)', text)
        if cas_match:
            data['cas_number'] = cas_match.group(1)

    return data


def identify_source_type(filename, text):
    """Identify the source type of a document."""
    filename_lower = filename.lower()
    text_lower = text[:1000].lower() if text else ''

    if 'ewg' in filename_lower or 'skin deep' in filename_lower:
        return 'ewg'
    elif 'pubchem' in filename_lower or 'pubchem' in text_lower:
        return 'pubchem'
    elif 'cosing' in filename_lower or 'cosing' in text_lower:
        return 'cosing'
    elif 'cosmetics info' in filename_lower:
        return 'cosmetics_info'
    elif 'wikipedia' in filename_lower:
        return 'wikipedia'
    else:
        return 'general'


def process_document(filepath):
    """Process a single document and extract ingredient data."""
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filename)[1].lower()

    # Extract ingredient name from filename
    ingredient_name = extract_ingredient_from_filename(filename)
    if not ingredient_name:
        return None, None

    # Extract text
    if ext == '.html':
        text = extract_text_from_html(filepath)
    elif ext == '.pdf':
        text = extract_text_from_pdf(filepath)
    else:
        return None, None

    if not text or len(text) < 100:
        return ingredient_name, {}

    # Identify source and extract data
    source_type = identify_source_type(filename, text)

    data = {}
    if source_type == 'ewg':
        data = extract_ewg_data(text, filename)
    elif source_type == 'pubchem':
        data = extract_pubchem_data(text, filename)
    elif source_type == 'cosing':
        data = extract_cosing_data(text, filename)

    # Always try to extract general data too
    general_data = extract_general_data(text, filename)
    for key, value in general_data.items():
        if key not in data:
            data[key] = value

    data['_source_file'] = filename
    data['_source_type'] = source_type

    return ingredient_name, data


def scan_devonthink_db():
    """Scan all documents in DevonThink database."""
    documents = []

    for root, dirs, files in os.walk(DEVONTHINK_DB):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in ('.html', '.pdf'):
                filepath = os.path.join(root, filename)
                documents.append(filepath)

    return documents


class WebflowUpdater:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.collection_id = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        self.items = []
        self.name_index = {}

    def fetch_all_items(self):
        """Fetch all ingredients from Webflow."""
        items = []
        offset = 0
        limit = 100

        while True:
            resp = requests.get(
                f'{WEBFLOW_API_BASE}/collections/{self.collection_id}/items',
                headers=self.headers,
                params={'offset': offset, 'limit': limit}
            )
            if not resp.ok:
                break

            batch = resp.json().get('items', [])
            items.extend(batch)

            if len(batch) < limit:
                break
            offset += limit
            if offset % 1000 == 0:
                print(f"  Fetched {offset}...")
            time.sleep(0.1)

        self.items = items

        # Build name index
        for item in items:
            name = item.get('fieldData', {}).get('name', '')
            if name:
                normalized = normalize_ingredient_name(name)
                self.name_index[normalized] = item

        return items

    def find_matching_item(self, ingredient_name):
        """Find matching Webflow item for an ingredient name."""
        normalized = normalize_ingredient_name(ingredient_name)

        # Exact match
        if normalized in self.name_index:
            return self.name_index[normalized]

        # Fuzzy match
        best_score = 0
        best_match = None
        for name, item in self.name_index.items():
            score = SequenceMatcher(None, normalized, name).ratio()
            if score > best_score and score > 0.85:
                best_score = score
                best_match = item

        return best_match

    def update_item(self, item_id, field_data, dry_run=True):
        """Update a Webflow item."""
        if dry_run:
            return True

        resp = requests.patch(
            f'{WEBFLOW_API_BASE}/collections/{self.collection_id}/items/{item_id}',
            headers=self.headers,
            json={'fieldData': field_data}
        )
        return resp.ok


def build_webflow_field_data(extracted_data, existing_data):
    """Convert extracted data to Webflow field format."""
    field_data = {}

    # Map extracted fields to Webflow fields
    if 'cas_number' in extracted_data:
        current = existing_data.get('cas-2', '')
        if not current:
            field_data['cas-2'] = extracted_data['cas_number']

    if 'ewg_score' in extracted_data:
        current = existing_data.get('ingredient-safety-score')
        if not current:
            field_data['ingredient-safety-score'] = extracted_data['ewg_score']

    if 'safety_concerns' in extracted_data:
        current = existing_data.get('safety-ratings-contraindications-2', '')
        if not current or len(current) < len(extracted_data['safety_concerns']):
            new_val = extracted_data['safety_concerns']
            if current:
                new_val = f"{current} | {new_val}"
            field_data['safety-ratings-contraindications-2'] = new_val[:500]

    if 'cosmetic_functions' in extracted_data:
        current = existing_data.get('functions-3', '')
        if not current:
            field_data['functions-3'] = extracted_data['cosmetic_functions'][:500]

    if 'benefits' in extracted_data:
        current = existing_data.get('support-details', '')
        if not current or len(current) < 50:
            field_data['support-details'] = extracted_data['benefits'][:500]

    if 'origin' in extracted_data:
        current = existing_data.get('origin-2', '')
        if not current:
            field_data['origin-2'] = extracted_data['origin'][:200]

    # Add to citations
    if 'source' in extracted_data and 'source_url' in extracted_data:
        current_citations = existing_data.get('how-we-know-references-mla-citations', '')
        source = extracted_data['source']
        url = extracted_data['source_url']
        citation = f'<li><a href="{url}" target="_blank">{source}</a></li>'

        if citation not in current_citations:
            if current_citations:
                # Add to existing list
                if '</ul>' in current_citations:
                    new_citations = current_citations.replace('</ul>', f'{citation}</ul>')
                else:
                    new_citations = f'{current_citations}\n<ul>{citation}</ul>'
            else:
                new_citations = f'<h4>Sources & References</h4>\n<ul>{citation}</ul>'
            field_data['how-we-know-references-mla-citations'] = new_citations

    return field_data


def main():
    dry_run = '--update' not in sys.argv
    limit = None
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    print("=" * 60)
    print("DEVONTHINK DATA EXTRACTOR")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print(f"Database: {DEVONTHINK_DB}")
    print()

    # Scan documents
    print("Scanning DevonThink database...")
    documents = scan_devonthink_db()
    print(f"Found {len(documents)} documents (HTML + PDF)")

    # Process documents
    print("\nExtracting data from documents...")
    extracted = {}
    source_counts = defaultdict(int)

    for i, filepath in enumerate(documents):
        if limit and i >= limit:
            break

        ingredient_name, data = process_document(filepath)

        if ingredient_name and data:
            normalized = normalize_ingredient_name(ingredient_name)
            if normalized not in extracted:
                extracted[normalized] = {'name': ingredient_name, 'data': {}}

            # Merge data
            for key, value in data.items():
                if key not in extracted[normalized]['data']:
                    extracted[normalized]['data'][key] = value

            source_type = data.get('_source_type', 'unknown')
            source_counts[source_type] += 1

        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1} documents...")

    print(f"\nExtracted data for {len(extracted)} ingredients")
    print("\nSource breakdown:")
    for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"  {source}: {count}")

    # Fetch Webflow items
    print("\nFetching Webflow ingredients...")
    updater = WebflowUpdater()
    items = updater.fetch_all_items()
    print(f"Found {len(items)} Webflow ingredients")

    # Match and prepare updates
    print("\nMatching extracted data to Webflow...")
    matched = 0
    updates = []

    for normalized, info in extracted.items():
        item = updater.find_matching_item(info['name'])
        if not item:
            continue

        matched += 1
        item_name = item.get('fieldData', {}).get('name', '')
        item_id = item.get('id', '')
        existing_data = item.get('fieldData', {})

        # Build update
        field_data = build_webflow_field_data(info['data'], existing_data)

        if field_data:
            updates.append({
                'id': item_id,
                'name': item_name,
                'source_name': info['name'],
                'field_data': field_data,
                'source_type': info['data'].get('_source_type', 'unknown'),
            })

    print(f"Matched: {matched}")
    print(f"Updates to apply: {len(updates)}")

    # Show or apply updates
    if dry_run:
        print("\n[DRY RUN] Sample updates:")
        for update in updates[:15]:
            print(f"\n  {update['source_name']} -> {update['name']} [{update['source_type']}]")
            print(f"    Fields: {list(update['field_data'].keys())}")
    else:
        print("\nApplying updates...")
        success = 0
        for i, update in enumerate(updates):
            result = updater.update_item(update['id'], update['field_data'], dry_run=False)
            if result:
                success += 1
            if (i + 1) % 50 == 0:
                print(f"  Updated {i + 1}/{len(updates)}...")
            time.sleep(0.3)
        print(f"\nSuccessfully updated: {success}/{len(updates)}")

    print("\n" + "=" * 60)
    if dry_run:
        print("To apply updates, run:")
        print("  python3 extract_devonthink.py --update")


if __name__ == '__main__':
    main()
