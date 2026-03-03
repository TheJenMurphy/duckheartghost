"""
Upload ingredient images to Webflow using Google Drive URLs.

Google Drive files are shared publicly and URLs are formatted for direct access.
Webflow CMS API accepts external URLs for image fields.
"""

import os
import sys
import time
import re
from pathlib import Path
from difflib import SequenceMatcher

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import requests
import subprocess
import json

WEBFLOW_API_BASE = "https://api.webflow.com/v2"
GDRIVE_FOLDER = "Ingredient Images/master"

# Image field slugs in order of priority (updated for new schema)
IMAGE_FIELDS = [
    'gallery-image-10',  # Hero
    'image-2',
    'image-3',
    'image-4',
    'image-5',
    'image-6',
    'image-7',
]

# Correct Ingredients collection ID
INGREDIENTS_COLLECTION_ID = '697d8cce1f942b01f173bcf2'


def strip_html(text):
    """Remove HTML tags from text."""
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', str(text)).strip()


def normalize_name(name):
    """Normalize ingredient name for matching."""
    name = strip_html(name)
    name = re.sub(r'\.(jpg|jpeg|png|gif|webp)$', '', name, flags=re.IGNORECASE)
    # Strip "(1)", "(2)", etc. duplicate suffixes
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)
    # Remove "Adobestock" + numbers
    name = re.sub(r'\s*adobestock\s*\d*', '', name, flags=re.IGNORECASE)
    name = name.strip().lower()
    name = name.replace('_', ' ')
    name = re.sub(r'\s+', ' ', name)
    return name


def clean_for_matching(name):
    """Clean name for fuzzy matching."""
    name = normalize_name(name)
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'\[^]]*\]', '', name)
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def generate_match_variants(name):
    """Generate multiple variants of a name for matching."""
    variants = set()
    normalized = normalize_name(name)
    variants.add(normalized)

    # 1. Strip common suffixes (glossary, page, header, jpg, png, copy, etc.)
    stripped = re.sub(r'\s*(glossary|page|header|block\d*|jpg|png|copy|extraxct|exttract)\s*$', '', normalized, flags=re.IGNORECASE).strip()
    if stripped and len(stripped) > 3:
        variants.add(stripped)

    # 2. Remove trailing numbers (aloe vera 1, aloe vera 2)
    no_trailing_num = re.sub(r'\s+\d+\s*$', '', normalized).strip()
    if no_trailing_num and len(no_trailing_num) > 3:
        variants.add(no_trailing_num)

    # 3. Normalize chemical numbers: "1 2 hexanediol" -> "1,2-hexanediol"
    chem_normalized = re.sub(r'(\d)\s+(\d)', r'\1,\2', normalized)
    chem_normalized = re.sub(r'(\d)\s*-\s*(\w)', r'\1-\2', chem_normalized)
    variants.add(chem_normalized)

    # 4. Try with commas between numbers
    with_commas = re.sub(r'(\d)\s+(\d)', r'\1,\2', normalized)
    variants.add(with_commas)

    # 5. Try with hyphens between numbers
    with_hyphens = re.sub(r'(\d)\s+(\d)', r'\1-\2', normalized)
    variants.add(with_hyphens)

    # 6. Remove parenthetical content (common names)
    no_parens = re.sub(r'\s*\([^)]*\)\s*', ' ', normalized).strip()
    no_parens = re.sub(r'\s+', ' ', no_parens)
    if no_parens and len(no_parens) > 3:
        variants.add(no_parens)

    # 7. Extract just the botanical name (first two words if Latin-looking)
    words = normalized.split()
    if len(words) >= 2 and re.match(r'^[a-z]+$', words[0]) and re.match(r'^[a-z]+$', words[1]):
        botanical = f"{words[0]} {words[1]}"
        if len(botanical) > 5:
            variants.add(botanical)

    # 8. Extract content from parentheses (common name)
    paren_match = re.search(r'\(([^)]+)\)', normalized)
    if paren_match:
        common_name = paren_match.group(1).strip()
        if common_name and len(common_name) > 3:
            variants.add(common_name)
            # Also try common name + "extract", "oil", etc.
            variants.add(f"{common_name} extract")
            variants.add(f"{common_name} oil")

    # 9. Handle "oil" suffix variations
    if normalized.endswith(' oil'):
        base = normalized[:-4].strip()
        if base:
            variants.add(base)
            variants.add(f"{base} seed oil")
            variants.add(f"{base} fruit oil")
            variants.add(f"{base} kernel oil")

    # 10. Add "extract" if not present
    if 'extract' not in normalized and 'oil' not in normalized:
        variants.add(f"{normalized} extract")

    # 11. Remove "extract" if present
    if normalized.endswith(' extract'):
        variants.add(normalized[:-8].strip())

    # 12. Clean version (only alphanumeric)
    clean = re.sub(r'[^a-z0-9\s]', '', normalized)
    clean = re.sub(r'\s+', ' ', clean).strip()
    if clean and len(clean) > 3:
        variants.add(clean)

    # 13. Peptide number normalization (hexapeptide 8 -> hexapeptide-8 -> hexapeptide8)
    peptide_match = re.search(r'((?:di|tri|tetra|penta|hexa|hepta|octa|nona|deca)?peptide)\s*[-]?\s*(\d+)', normalized)
    if peptide_match:
        base_peptide = peptide_match.group(1)
        num = peptide_match.group(2)
        variants.add(f"{base_peptide}-{num}")
        variants.add(f"{base_peptide}{num}")
        variants.add(f"{base_peptide} {num}")
        # Also add prefixed versions
        prefix_match = re.match(r'^(\w+)\s+' + re.escape(base_peptide), normalized)
        if prefix_match:
            prefix = prefix_match.group(1)
            variants.add(f"{prefix} {base_peptide}-{num}")
            variants.add(f"{prefix} {base_peptide}{num}")

    # 14. Polyglyceryl number normalization (polyglyceryl 6 -> polyglyceryl-6)
    poly_match = re.search(r'(polyglyceryl|polyglycerin)\s*[-]?\s*(\d+)', normalized)
    if poly_match:
        num = poly_match.group(2)
        variants.add(f"polyglyceryl-{num}")
        variants.add(f"polyglyceryl{num}")
        variants.add(f"polyglyceryl {num}")
        variants.add(f"polyglycerin-{num}")
        variants.add(f"polyglycerin{num}")
        variants.add(f"polyglycerin {num}")

    # Also handle just "polyglycerin 3" without a number (rare but exists)
    if 'polyglycerin' in normalized and 'polyglyceryl' not in normalized:
        variants.add(normalized.replace('polyglycerin', 'polyglyceryl'))

    # 15. Beta/alpha prefix normalization (beta sitosterol -> beta-sitosterol)
    greek_match = re.search(r'^(alpha|beta|gamma|delta)\s+(\w+)', normalized)
    if greek_match:
        greek = greek_match.group(1)
        rest = greek_match.group(2)
        variants.add(f"{greek}-{rest}")
        variants.add(f"{greek}{rest}")

    # 16. Handle "acid" suffix variations
    if normalized.endswith(' acid'):
        base = normalized[:-5].strip()
        if base:
            variants.add(base)
            # Common acid aliases
            variants.add(f"{base}ic acid")

    # 17. Common chemical aliases
    common_aliases = {
        'hyaluronic acid': ['sodium hyaluronate', 'ha', 'hyaluronan'],
        'sodium hyaluronate': ['hyaluronic acid', 'ha', 'hyaluronan'],
        'vitamin c': ['ascorbic acid', 'l-ascorbic acid'],
        'ascorbic acid': ['vitamin c', 'l-ascorbic acid'],
        'vitamin e': ['tocopherol', 'tocopheryl acetate'],
        'tocopherol': ['vitamin e'],
        'retinol': ['vitamin a', 'retinyl palmitate'],
        'vitamin a': ['retinol', 'retinyl palmitate'],
        'niacinamide': ['vitamin b3', 'nicotinamide'],
        'vitamin b3': ['niacinamide', 'nicotinamide'],
        'glycerin': ['glycerol', 'glycerine'],
        'glycerol': ['glycerin', 'glycerine'],
        'cetyl alcohol': ['1-hexadecanol', 'palmityl alcohol'],
        'stearic acid': ['octadecanoic acid'],
        'caprylic acid': ['octanoic acid'],
        'capric acid': ['decanoic acid'],
        'lauric acid': ['dodecanoic acid'],
        'oleic acid': ['cis-9-octadecenoic acid'],
        'linoleic acid': ['cis,cis-9,12-octadecadienoic acid'],
        'phenoxyethanol': ['2-phenoxyethanol', 'phenoxytol'],
        'panthenol': ['vitamin b5', 'provitamin b5', 'd-panthenol'],
        'dimethicone': ['polydimethylsiloxane', 'pdms'],
        'silicone': ['dimethicone', 'polydimethylsiloxane'],
        'aloe': ['aloe vera', 'aloe barbadensis'],
        'aloe vera': ['aloe', 'aloe barbadensis', 'aloe barbadensis leaf juice'],
        'chamomile': ['chamomilla recutita', 'matricaria chamomilla', 'anthemis nobilis'],
        'lavender': ['lavandula angustifolia', 'lavandula officinalis'],
        'rosemary': ['rosmarinus officinalis'],
        'tea tree': ['melaleuca alternifolia'],
        'jojoba': ['simmondsia chinensis'],
        'argan': ['argania spinosa'],
        'shea butter': ['butyrospermum parkii', 'vitellaria paradoxa'],
        'coconut oil': ['cocos nucifera oil'],
        'olive oil': ['olea europaea oil'],
        'sunflower oil': ['helianthus annuus seed oil'],
        'castor oil': ['ricinus communis seed oil'],
        'grapeseed oil': ['vitis vinifera seed oil'],
        'sweet almond oil': ['prunus amygdalus dulcis oil'],
        'arnica': ['arnica montana'],
        'calendula': ['calendula officinalis'],
        'ginseng': ['panax ginseng'],
        'green tea': ['camellia sinensis'],
        'witch hazel': ['hamamelis virginiana'],
        'alginate': ['algin', 'sodium alginate'],
        'sodium alginate': ['alginate', 'algin'],
        'camellia': ['camellia sinensis', 'camellia japonica', 'camellia oleifera'],
        'camellia seed oil': ['camellia oleifera seed oil', 'camellia japonica seed oil'],
        'camelina oil': ['camelina sativa seed oil'],
        'lactic acid': ['lactate', '2-hydroxypropanoic acid'],
        'cetyl alcohol': ['1-hexadecanol', 'palmityl alcohol', 'hexadecan-1-ol'],
        'carminic acid': ['carmine', 'cochineal extract', 'ci 75470'],
        'hyaluronic acid': ['sodium hyaluronate', 'ha', 'hyaluronan', 'hyaluronate'],
        'caprylic capric triglyceride': ['caprylic/capric triglyceride', 'mct oil', 'medium chain triglycerides'],
        'rosehip seed oil': ['rosa canina seed oil', 'rosa rubiginosa seed oil'],
        'rosehip oil': ['rosa canina seed oil', 'rosa rubiginosa seed oil'],
        'matcha': ['camellia sinensis leaf powder', 'tea matcha', 'matcha green tea'],
        'phenethyl alcohol': ['phenylethyl alcohol', '2-phenylethanol', 'benzyl carbinol'],
        'tocopherols': ['tocopherol', 'vitamin e', 'mixed tocopherols'],
        'glyceryl monostearate': ['glyceryl stearate', 'glycerol monostearate'],
        'willow bark extract': ['salix alba bark extract', 'salix nigra bark extract'],
        'lemongrass': ['cymbopogon citratus', 'cymbopogon flexuosus'],
        'lemongrass essential oil': ['cymbopogon citratus oil', 'cymbopogon flexuosus oil'],
        'chrysanthemum': ['chrysanthemum indicum', 'chrysanthemum morifolium'],
        'chickory': ['chicory', 'cichorium intybus'],
        'chicory': ['chicory root', 'cichorium intybus'],
        'adzuki': ['azuki', 'adzuki bean', 'vigna angularis'],
        'azuki': ['adzuki', 'adzuki bean', 'vigna angularis'],
        'burdock': ['arctium lappa', 'burdock root'],
        'lindenflower': ['linden flower', 'tilia'],
        'raspberry': ['rubus idaeus'],
        'raspberry leaf': ['rubus idaeus leaf', 'rubus idaeus leaf extract'],
        'rose petals': ['rosa centifolia flower', 'rosa damascena flower'],
        'soybeans': ['soybean', 'glycine max', 'soy'],
        'plum': ['prunus domestica'],
        'mandarin': ['citrus reticulata', 'citrus nobilis'],
        'parsley': ['petroselinum crispum', 'petroselinum sativum'],
        'nylon 12': ['nylon-12'],
        'nylon-12': ['nylon 12'],
        'blood orange': ['citrus sinensis', 'red orange'],
        'kukui nut': ['aleurites moluccana', 'kukui nut oil', 'candlenut'],
        'kukui': ['aleurites moluccana', 'kukui nut oil'],
        'argan tree': ['argania spinosa', 'argan oil', 'argan kernel oil'],
        'dandelion': ['taraxacum officinale'],
        'dandelion leaves': ['taraxacum officinale leaf', 'dandelion leaf extract'],
        'green tangerine': ['citrus reticulata', 'citrus unshiu'],
        'yucca': ['yucca schidigera', 'yucca root'],
        'yucca root': ['yucca schidigera'],
        'ginkgo biloba': ['ginkgo biloba leaf', 'ginkgo biloba extract'],
        'gingko biloba': ['ginkgo biloba leaf', 'ginkgo biloba extract'],
        'himalayan salt': ['sodium chloride', 'himalayan pink salt'],
        'himalayan sea salt': ['sodium chloride', 'himalayan pink salt'],
        'jojoba seeds': ['simmondsia chinensis seed', 'jojoba seed oil'],
        'saffron': ['crocus sativus'],
        'saffron flowers': ['crocus sativus flower'],
        'melissa': ['melissa officinalis', 'lemon balm'],
        'melissa essential oil': ['melissa officinalis oil'],
        'davana': ['artemisia pallens'],
        'davana essential oil': ['artemisia pallens oil'],
        'cistus': ['cistus ladaniferus', 'rockrose'],
        'cistus essential oil': ['cistus ladaniferus oil'],
        'virginia cedarwood': ['juniperus virginiana', 'cedrus'],
        'virginia cedarwood essential oil': ['juniperus virginiana oil'],
        'carrot seed': ['daucus carota', 'carrot seed oil'],
        'seed carrot': ['daucus carota seed', 'carrot seed oil'],
        'rose': ['rosa damascena', 'rosa centifolia'],
        'rose flower extract': ['rosa damascena flower extract', 'rosa centifolia flower extract'],
        'sandalwood': ['santalum album'],
        'sandalwood essential oil': ['santalum album oil', 'sandalwood oil'],
        'orange essential oil': ['citrus aurantium dulcis oil', 'citrus sinensis oil'],
        'lemon essential oil': ['citrus limon peel oil'],
        'eucalyptus': ['eucalyptus globulus'],
        'peppermint': ['mentha piperita'],
        'thyme': ['thymus vulgaris'],
        'sage': ['salvia officinalis'],
    }

    if normalized in common_aliases:
        for alias in common_aliases[normalized]:
            variants.add(alias)

    # Also check partial matches
    for key, aliases in common_aliases.items():
        if key in normalized:
            for alias in aliases:
                variants.add(normalized.replace(key, alias))

    # 18. Remove "essential oil" -> just "oil"
    if 'essential oil' in normalized:
        variants.add(normalized.replace('essential oil', 'oil'))

    # 19. Triglyceride variations
    if 'triglyceride' in normalized:
        variants.add(normalized.replace('triglyceride', 'triglycerides'))
    if 'triglycerides' in normalized:
        variants.add(normalized.replace('triglycerides', 'triglyceride'))

    # 20. Caprylic/capric variations
    if 'caprylic capric' in normalized:
        variants.add(normalized.replace('caprylic capric', 'caprylic/capric'))
        variants.add(normalized.replace('caprylic capric', 'capric/caprylic'))
    if 'capric caprylic' in normalized:
        variants.add(normalized.replace('capric caprylic', 'caprylic/capric'))

    # 21. Common typo corrections
    typo_fixes = {
        'maritum': 'maritimum',
        'extraxct': 'extract',
        'exttract': 'extract',
        'chickory': 'chicory',
        'azuki': 'adzuki',
        'canabis': 'cannabis',
        'squae': 'square',
        'lindenflower': 'linden flower',
        'manderin': 'mandarin',
        'tequiliana': 'tequilana',
        'morifolium': 'indicum',
        'isp': '',
        'oxyychloride': 'oxychloride',
        'calenula': 'calendula',
        'gingko': 'ginkgo',
        'phenoxyethenol': 'phenoxyethanol',
        'brassic': 'brassica',
        'oleifera': 'oleifera',
        'hempseeds': 'hemp seed',
        'hempseed': 'hemp seed',
        'tangerine': 'mandarin',
        'sucrose monostearate': 'sucrose stearate',
        'monostearate': 'stearate',
    }
    for typo, fix in typo_fixes.items():
        if typo in normalized:
            fixed = normalized.replace(typo, fix).strip()
            fixed = re.sub(r'\s+', ' ', fixed)
            if fixed and len(fixed) > 3:
                variants.add(fixed)

    # 22. Di-ppg, ppg patterns (di ppg 2 -> di-ppg-2)
    if 'ppg' in normalized:
        ppg_fixed = re.sub(r'(\bdi\s+ppg\s*)(\d+)', r'di-ppg-\2', normalized)
        variants.add(ppg_fixed)
        ppg_fixed = re.sub(r'\bppg\s+(\d+)', r'ppg-\1', normalized)
        variants.add(ppg_fixed)

    # 23. N-acetyl patterns
    if 'n acetyl' in normalized:
        variants.add(normalized.replace('n acetyl', 'n-acetyl'))
        variants.add(normalized.replace('n acetyl', 'acetyl'))

    # 24. Handle "stalk", "leaf", "root", "flower" suffix variations
    for plant_part in ['stalk', 'leaf', 'root', 'flower', 'seed', 'bark', 'fruit', 'peel']:
        if normalized.endswith(f' {plant_part}'):
            base = normalized[:-len(plant_part)-1].strip()
            if base and len(base) > 3:
                variants.add(base)
                variants.add(f"{base} extract")
                variants.add(f"{base} oil")

    # 25. Handle "a rosemary stalk" -> "rosemary"
    if normalized.startswith('a '):
        variants.add(normalized[2:].strip())

    return variants


def extract_key_terms(name):
    """Extract key searchable terms from ingredient name."""
    normalized = normalize_name(name)
    terms = set()

    # Split into words
    words = normalized.split()

    # Add individual significant words (length > 4)
    for word in words:
        clean_word = re.sub(r'[^a-z]', '', word)
        if len(clean_word) > 4:
            terms.add(clean_word)

    # Add bigrams
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        terms.add(bigram)

    return terms


def similarity(a, b):
    """Calculate similarity ratio."""
    return SequenceMatcher(None, a, b).ratio()


def is_junk_name(name):
    """Check if ingredient name is junk."""
    junk = {'ext', 'pharmaceutical secondary standard', '1', '2', '3', '3s', 'powder', 'puriss'}
    normalized = normalize_name(name)
    if normalized in junk:
        return True
    if len(normalized) <= 3:
        return True
    if normalized.startswith('●'):
        return True
    return False


def classify_image(filename):
    """Classify image type based on filename."""
    lower = filename.lower()

    # Hero indicators
    hero_patterns = ['on white', 'white background', 'transparent', 'isolated',
                     'studio', 'product shot', 'cutout', 'hero_', 'hero-',
                     'clean background', 'white bg', 'pure white']
    for pattern in hero_patterns:
        if pattern in lower:
            return 'hero'

    # Field indicators
    field_patterns = ['field', 'branch', 'plant', 'tree', 'growing', 'farm',
                      'nature', 'outdoor', 'wild', 'garden', 'field_', 'field-']
    for pattern in field_patterns:
        if pattern in lower:
            return 'field'

    return 'other'


def get_gdrive_file_id(remote_path):
    """Get Google Drive file ID for a path using rclone."""
    try:
        result = subprocess.run(
            ['rclone', 'lsjson', f'gdrive:{remote_path}'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            files = json.loads(result.stdout)
            if files and len(files) > 0:
                return files[0].get('ID')
    except Exception as e:
        pass
    return None


def get_gdrive_direct_url(file_id):
    """Convert file ID to direct download URL."""
    # This URL format allows Webflow to fetch the image
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def list_gdrive_folders():
    """List all ingredient folders in Google Drive."""
    try:
        result = subprocess.run(
            ['rclone', 'lsjson', f'gdrive:{GDRIVE_FOLDER}'],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            items = json.loads(result.stdout)
            folders = [i for i in items if i.get('IsDir')]
            return folders
    except Exception as e:
        print(f"Error listing folders: {e}")
    return []


def list_folder_images(folder_name):
    """List images in a folder."""
    try:
        result = subprocess.run(
            ['rclone', 'lsjson', f'gdrive:{GDRIVE_FOLDER}/{folder_name}'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            items = json.loads(result.stdout)
            images = [i for i in items if not i.get('IsDir') and
                      i.get('Name', '').lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
            return images
    except Exception as e:
        pass
    return []


def pick_best_images(images, max_images=6):
    """Pick best images for each slot."""
    result = {}

    # Classify all images
    classified = {'hero': [], 'field': [], 'other': []}
    for img in images:
        img_type = classify_image(img.get('Name', ''))
        classified[img_type].append(img)

    # Sort each category by size (larger = better quality)
    for cat in classified:
        classified[cat].sort(key=lambda x: x.get('Size', 0), reverse=True)

    slots = ['hero', 'field', 'g3', 'g4', 'g5', 'g6', 'g7']
    used = set()

    # Assign hero
    for img in classified['hero']:
        if img['ID'] not in used:
            result['hero'] = img
            used.add(img['ID'])
            break

    # Assign field
    for img in classified['field']:
        if img['ID'] not in used:
            result['field'] = img
            used.add(img['ID'])
            break

    # Fill remaining slots with other images
    all_remaining = [img for cat in ['other', 'hero', 'field']
                     for img in classified[cat] if img['ID'] not in used]

    for slot in ['g3', 'g4', 'g5', 'g6', 'g7']:
        if all_remaining:
            img = all_remaining.pop(0)
            result[slot] = img
            used.add(img['ID'])

    return result


class WebflowUploader:
    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.collection_id = INGREDIENTS_COLLECTION_ID  # Use hardcoded correct ID
        self.site_id = os.environ.get('WEBFLOW_SITE_ID', '')

        if not self.api_token:
            raise ValueError("Missing WEBFLOW_API_TOKEN")

        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    def get_all_ingredients(self):
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
                print(f"Error fetching: {resp.status_code}")
                break

            data = resp.json()
            batch = data.get('items', [])
            items.extend(batch)

            if len(batch) < limit:
                break
            offset += limit
            if offset % 1000 == 0:
                print(f"  Fetched {offset}...")
            time.sleep(0.1)

        return items

    def update_item_images(self, item_id, item_name, image_urls, dry_run=True, debug=False):
        """Update item with image URLs."""
        field_data = {
            'name': item_name,  # Required field for Webflow PATCH
        }

        slot_to_field = {
            'hero': 'gallery-image-10',
            'field': 'image-2',
            'g3': 'image-3',
            'g4': 'image-4',
            'g5': 'image-5',
            'g6': 'image-6',
            'g7': 'image-7',
        }

        for slot, url in image_urls.items():
            field = slot_to_field.get(slot)
            if field and url:
                field_data[field] = {'url': url}

        if len(field_data) <= 1:  # Only name, no images
            return False

        if dry_run:
            return True

        payload = {'fieldData': field_data}
        if debug:
            import json
            print(f"\n  Payload: {json.dumps(payload, indent=2)[:500]}")

        resp = requests.patch(
            f'{WEBFLOW_API_BASE}/collections/{self.collection_id}/items/{item_id}',
            headers=self.headers,
            json=payload
        )

        if not resp.ok:
            print(f" Error {resp.status_code}: {resp.text[:300]}")
        return resp.ok

    def process(self, dry_run=True, limit=None):
        """Process all folders and update Webflow."""
        print("=" * 50, flush=True)
        print("GOOGLE DRIVE -> WEBFLOW IMAGE UPLOADER", flush=True)
        print("=" * 50, flush=True)
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}", flush=True)
        print(flush=True)

        # Get Google Drive folders
        print("Listing Google Drive folders...")
        folders = list_gdrive_folders()
        print(f"Found {len(folders)} ingredient folders")

        if not folders:
            print("No folders found. Has the sync completed?")
            return

        # Get Webflow ingredients
        print("\nFetching Webflow ingredients...")
        items = self.get_all_ingredients()
        print(f"Found {len(items)} Webflow ingredients")

        # Build indices (by name AND by INCI name)
        exact_index = {}
        clean_index = {}
        inci_index = {}
        variant_index = {}  # Maps variants to items
        term_index = {}  # Maps key terms to items

        for item in items:
            fd = item.get('fieldData', {})
            name = fd.get('name', '')
            inci = strip_html(fd.get('inci-name', ''))

            if name and not is_junk_name(name):
                exact_index[normalize_name(name)] = item
                clean_index[clean_for_matching(name)] = item
                # Generate variants for display name
                for variant in generate_match_variants(name):
                    if variant not in variant_index:
                        variant_index[variant] = item
                # Index key terms
                for term in extract_key_terms(name):
                    if term not in term_index:
                        term_index[term] = []
                    term_index[term].append(item)

            # Also index by INCI name (primary match for Google Drive images)
            if inci and not is_junk_name(inci):
                inci_index[normalize_name(inci)] = item
                clean_index[clean_for_matching(inci)] = item
                # Generate variants for INCI name
                for variant in generate_match_variants(inci):
                    if variant not in variant_index:
                        variant_index[variant] = item
                # Index key terms
                for term in extract_key_terms(inci):
                    if term not in term_index:
                        term_index[term] = []
                    term_index[term].append(item)

        print(f"Built indices: {len(inci_index)} INCI, {len(exact_index)} names, {len(variant_index)} variants")

        # Process folders
        matched = 0
        updated = 0

        for i, folder in enumerate(folders):
            if limit and i >= limit:
                break

            folder_name = folder.get('Name', '')

            # Find matching Webflow item using multiple strategies
            item = None

            # Strategy 1: Generate variants for folder name and check all indices
            folder_variants = generate_match_variants(folder_name)
            for variant in folder_variants:
                if variant in inci_index:
                    item = inci_index[variant]
                    break
                if variant in exact_index:
                    item = exact_index[variant]
                    break
                if variant in variant_index:
                    item = variant_index[variant]
                    break
                if variant in clean_index:
                    item = clean_index[variant]
                    break

            # Strategy 2: Try similarity matching with lower threshold
            if not item:
                normalized = normalize_name(folder_name)
                best_score = 0
                for inci, candidate in inci_index.items():
                    score = similarity(normalized, inci)
                    if score > best_score and score > 0.70:
                        best_score = score
                        item = candidate

            # Strategy 3: Try matching variants against all indices with similarity
            if not item:
                best_score = 0
                for variant in folder_variants:
                    for inci, candidate in inci_index.items():
                        score = similarity(variant, inci)
                        if score > best_score and score > 0.75:
                            best_score = score
                            item = candidate
                    if best_score > 0.90:  # Early exit if great match
                        break

            # Strategy 3.5: Try against display names too
            if not item:
                best_score = 0
                for variant in folder_variants:
                    for name, candidate in exact_index.items():
                        score = similarity(variant, name)
                        if score > best_score and score > 0.75:
                            best_score = score
                            item = candidate

            # Strategy 4: Key term matching (find items that share significant terms)
            if not item:
                folder_terms = extract_key_terms(folder_name)
                term_matches = {}
                for term in folder_terms:
                    if term in term_index:
                        for candidate in term_index[term]:
                            cid = candidate.get('id')
                            if cid not in term_matches:
                                term_matches[cid] = {'item': candidate, 'count': 0}
                            term_matches[cid]['count'] += 1

                # Pick item with most matching terms
                if term_matches:
                    best = max(term_matches.values(), key=lambda x: x['count'])
                    if best['count'] >= 2:  # Require at least 2 matching terms
                        item = best['item']

            # Strategy 5: Partial match - check if folder name contains/is contained by INCI
            if not item:
                normalized = normalize_name(folder_name)
                for inci, candidate in inci_index.items():
                    # Folder name contains INCI
                    if len(inci) > 5 and inci in normalized:
                        item = candidate
                        break
                    # INCI contains folder name
                    if len(normalized) > 5 and normalized in inci:
                        item = candidate
                        break

            if not item:
                continue

            matched += 1
            item_name = item.get('fieldData', {}).get('name', '')
            item_id = item.get('id', '')

            # Get images in folder
            images = list_folder_images(folder_name)
            if not images:
                continue

            # Pick best images
            best = pick_best_images(images)

            # Build URLs
            image_urls = {}
            for slot, img in best.items():
                file_id = img.get('ID')
                if file_id:
                    image_urls[slot] = get_gdrive_direct_url(file_id)

            if not image_urls:
                continue

            # Update
            if dry_run:
                print(f"\n[{matched}] {folder_name} -> {item_name}")
                print(f"  Would upload: {list(image_urls.keys())}")
            else:
                print(f"[{matched}] Updating {item_name[:50]}...", end=' ', flush=True)
                success = self.update_item_images(item_id, item_name, image_urls, dry_run=False, debug=(matched <= 2))
                if success:
                    updated += 1
                    print("OK")
                else:
                    print("FAILED")
                time.sleep(0.3)  # Rate limiting

        print("\n" + "=" * 50, flush=True)
        print("SUMMARY", flush=True)
        print("=" * 50, flush=True)
        print(f"Folders:  {len(folders)}", flush=True)
        print(f"Matched:  {matched}", flush=True)
        if not dry_run:
            print(f"Updated:  {updated}", flush=True)

        if dry_run:
            print("\nTo upload, run:")
            print("  python3 upload_via_gdrive.py --upload")

    def diagnose_unmatched(self):
        """Show unmatched folders for debugging."""
        print("=" * 50)
        print("DIAGNOSING UNMATCHED FOLDERS")
        print("=" * 50)

        # Get folders
        folders = list_gdrive_folders()
        print(f"Total folders: {len(folders)}")

        # Get ingredients
        items = self.get_all_ingredients()
        print(f"Total ingredients: {len(items)}")

        # Build all indices
        all_names = set()
        for item in items:
            fd = item.get('fieldData', {})
            name = fd.get('name', '')
            inci = strip_html(fd.get('inci-name', ''))
            if name:
                all_names.add(normalize_name(name))
                for v in generate_match_variants(name):
                    all_names.add(v)
            if inci:
                all_names.add(normalize_name(inci))
                for v in generate_match_variants(inci):
                    all_names.add(v)

        # Find unmatched
        unmatched = []
        for folder in folders:
            folder_name = folder.get('Name', '')
            variants = generate_match_variants(folder_name)

            matched = False
            for v in variants:
                if v in all_names:
                    matched = True
                    break

            if not matched:
                # Check similarity
                normalized = normalize_name(folder_name)
                best_score = 0
                best_match = None
                for name in list(all_names)[:1000]:  # Sample for speed
                    score = similarity(normalized, name)
                    if score > best_score:
                        best_score = score
                        best_match = name

                unmatched.append((folder_name, best_score, best_match))

        print(f"\nUnmatched folders: {len(unmatched)}")
        print("\nSample unmatched (first 50):")
        for fname, score, best in sorted(unmatched, key=lambda x: -x[1])[:50]:
            print(f"  {fname[:45]:45} score={score:.2f} -> {best[:35] if best else 'None'}")


def main():
    dry_run = '--upload' not in sys.argv
    diagnose = '--diagnose' in sys.argv
    limit = None
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])

    uploader = WebflowUploader()

    if diagnose:
        uploader.diagnose_unmatched()
    else:
        uploader.process(dry_run=dry_run, limit=limit)


if __name__ == '__main__':
    main()
