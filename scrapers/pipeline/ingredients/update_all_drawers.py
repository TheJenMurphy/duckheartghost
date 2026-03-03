"""
Comprehensive Webflow Drawer Update - Uses ALL available data sources.

Merges data from:
- SQLite database (EWG, CIR, PubChem, botanical info)
- CosIng CSV (functions, benefits, features, EU regulatory, concentrations)

Drawer Fields:
1. what-it-is - IDENTITY ONLY: INCI, common names, CAS, EC, type, form, plant family
2. what-it-does - FUNCTIONS: What the ingredient does, benefits, features, how it works
3. how-it-s-made - Chemistry: molecular info, source, process
4. who-it-s-for - Suitability: skin types, safety, warnings, EWG/CIR
5. how-we-know - References: EWG, CIR, PubChem, CosIng, SCCS
"""

import csv
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import requests

from .database import IngredientDatabase
from .models import IngredientData

# Paths
CSV_FILE = Path(__file__).parent.parent / "data" / "cosing_9s_mapped.csv"
WEBFLOW_API_BASE = "https://api.webflow.com/v2"


def load_cosing_data() -> Dict[str, Dict]:
    """Load CosIng CSV data indexed by INCI name."""
    data = {}
    if not CSV_FILE.exists():
        print(f"Warning: CosIng CSV not found at {CSV_FILE}")
        return data

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            inci = row.get('inci_name', '').strip()
            if inci:
                data[inci.lower()] = row
    return data


def infer_type(ing: IngredientData, cosing: Dict) -> str:
    """Infer ingredient type from all available data."""
    name_lower = ing.inci_name.lower()
    func_lower = (ing.function or cosing.get('functions', '') or '').lower()

    if ing.plant_family or ing.plant_part:
        return "Botanical"
    if any(kw in name_lower for kw in ['extract', 'flower', 'leaf', 'root', 'bark', 'seed', 'fruit', 'peel']):
        return "Botanical"
    if any(x in name_lower for x in ['vitamin ', 'retinol', 'tocopherol', 'ascorb', 'niacin', 'panthen']):
        return "Vitamin"
    if any(x in name_lower for x in ['mica', 'silica', 'zinc oxide', 'titanium dioxide', 'water', 'aqua', 'iron oxide']):
        return "Mineral"
    if any(x in name_lower for x in ['ferment', 'lactobacillus', 'saccharomyces', 'biosaccharide', 'bifida']):
        return "Fermented"
    if any(x in name_lower for x in [' oil', 'seed oil', 'kernel oil', 'butter', ' wax', ' cera']):
        return "Plant-Derived"
    if any(x in name_lower for x in ['dimethicone', 'silicone', 'peg-', 'ppg-', 'acrylate', 'polymer', 'polyglyceryl']):
        return "Synthetic"
    if 'fragrance' in func_lower or 'perfum' in func_lower:
        return "Fragrance"
    return "Synthetic"


def infer_form(ing: IngredientData) -> str:
    """Infer ingredient form."""
    if ing.form:
        return ing.form.title()

    name_lower = ing.inci_name.lower()
    if any(x in name_lower for x in [' oil', 'seed oil', 'kernel oil', 'fruit oil']):
        return "Oil"
    if any(x in name_lower for x in [' butter', 'shea butter', 'cocoa butter']):
        return "Butter"
    if any(x in name_lower for x in [' wax', 'beeswax', 'candelilla', ' cera']):
        return "Wax"
    if any(x in name_lower for x in [' powder', 'mica', 'talc', 'silica', 'kaolin', 'clay', 'oxide']):
        return "Powder"
    if any(x in name_lower for x in [' extract', 'leaf extract', 'root extract', 'flower extract']):
        return "Extract"
    if any(x in name_lower for x in ['water', 'aqua', 'hydrosol']):
        return "Liquid"
    if any(x in name_lower for x in ['glycerin', 'alcohol', 'dimethicone']):
        return "Liquid"
    if any(x in name_lower for x in ['acid']):
        return "Powder/Crystal"
    return None


# ============================================================================
# DRAWER BUILDERS - Using ALL available data
# ============================================================================

def build_what_it_is(ing: IngredientData, cosing: Dict) -> str:
    """
    WHAT IT IS drawer - IDENTITY ONLY.
    Contains: INCI, common names, CAS, EC, type, form, plant family, plant part, origin.
    NO functions, benefits, or descriptions of what it does (those go in WHAT IT DOES).
    """
    parts = []

    # INCI Name (always present)
    parts.append(f"<p><strong>INCI Name:</strong> <em>{ing.inci_name}</em></p>")

    # Common Names
    if ing.common_names:
        names = ', '.join(ing.common_names[:5])
        parts.append(f"<p><strong>Also Known As:</strong> {names}</p>")

    # Type
    ing_type = infer_type(ing, cosing)
    parts.append(f"<p><strong>Type:</strong> {ing_type}</p>")

    # Kind (if different from type)
    if ing.kind and ing.kind.lower() != ing_type.lower():
        parts.append(f"<p><strong>Category:</strong> {ing.kind}</p>")

    # Form
    form = infer_form(ing)
    if form:
        parts.append(f"<p><strong>Form:</strong> {form}</p>")

    # Plant info
    if ing.plant_family:
        parts.append(f"<p><strong>Plant Family:</strong> <em>{ing.plant_family}</em></p>")
    if ing.plant_part:
        parts.append(f"<p><strong>Plant Part:</strong> {ing.plant_part}</p>")

    # Origin
    if ing.origin:
        parts.append(f"<p><strong>Origin:</strong> {ing.origin}</p>")

    # Chemical identifiers
    cas = ing.cas_number or cosing.get('cas_no', '')
    if cas:
        parts.append(f"<p><strong>CAS Number:</strong> {cas}</p>")
    if ing.ec_number:
        parts.append(f"<p><strong>EC Number:</strong> {ing.ec_number}</p>")

    return ''.join(parts)


def build_how_its_made(ing: IngredientData, cosing: Dict) -> str:
    """
    HOW IT'S MADE drawer - Chemistry and production process.
    Uses: molecular formula, molecular weight, process, source.
    NOTE: chemistry_nutrients moved to WHAT IT DOES drawer.
    """
    parts = []

    # Molecular info from PubChem
    if ing.molecular_formula:
        parts.append(f"<p><strong>Molecular Formula:</strong> {ing.molecular_formula}</p>")
    if ing.molecular_weight:
        parts.append(f"<p><strong>Molecular Weight:</strong> {ing.molecular_weight:.2f} g/mol</p>")

    # Process/extraction method
    if ing.process:
        parts.append(f"<p><strong>Process:</strong> {ing.process}</p>")
    else:
        # Infer process from name
        name_lower = ing.inci_name.lower()
        if 'extract' in name_lower:
            parts.append("<p><strong>Process:</strong> Extracted from plant material</p>")
        elif 'ferment' in name_lower:
            parts.append("<p><strong>Process:</strong> Produced through fermentation</p>")
        elif any(x in name_lower for x in ['cold pressed', 'cold-pressed']):
            parts.append("<p><strong>Process:</strong> Cold pressed</p>")
        elif 'distilled' in name_lower or 'essential oil' in name_lower:
            parts.append("<p><strong>Process:</strong> Steam distilled</p>")

    # Source/origin details
    if ing.plant_part and ing.plant_family:
        parts.append(f"<p><strong>Source:</strong> Derived from {ing.plant_part.lower()} of {ing.plant_family} plants</p>")

    return ''.join(parts)


def build_what_it_does(ing: IngredientData, cosing: Dict) -> Dict[str, str]:
    """
    WHAT IT DOES drawer - Functions, benefits, how it works.
    Returns dict with:
      - 'what-it-does': Rich text drawer content
      - 'functions-3': Plain text functions
      - 'medicine', 'aromatherapy', 'scent': Additional fields
    """
    fields = {}
    drawer_parts = []

    # Functions - combine database and CosIng
    functions = []
    if ing.function:
        functions.append(ing.function)
    if cosing.get('functions'):
        cosing_funcs = cosing.get('functions', '').replace(' | ', ', ')
        if cosing_funcs and cosing_funcs not in functions:
            functions.append(cosing_funcs)

    if functions:
        fields['functions-3'] = ' | '.join(functions)
        drawer_parts.append(f"<p><strong>Functions:</strong> {', '.join(functions)}</p>")

    # Description - what this ingredient does (moved from WHAT IT IS)
    desc = ing.description or cosing.get('chemical_description', '')
    if desc:
        desc = desc.strip()[:500]
        if len(desc) == 500:
            desc += "..."
        drawer_parts.append(f"<p><strong>Description:</strong> {desc}</p>")

    # Benefits from CosIng
    benefits = cosing.get('benefits', '')
    if benefits:
        drawer_parts.append(f"<p><strong>Benefits:</strong> {benefits}</p>")

    # Features / How it works from CosIng
    features = cosing.get('features', '')
    if features:
        drawer_parts.append(f"<p><strong>How It Works:</strong> {features}</p>")

    # Chemistry/nutrients info (how it works at a chemical level)
    if ing.chemistry_nutrients:
        drawer_parts.append(f"<p><strong>Active Compounds:</strong> {ing.chemistry_nutrients}</p>")

    # Medicinal uses
    if ing.medicinal_uses:
        drawer_parts.append(f"<p><strong>Traditional Uses:</strong> {ing.medicinal_uses}</p>")
        fields['medicine'] = f"<p>{ing.medicinal_uses}</p>"

    # Aromatherapy
    if ing.aromatherapy_uses:
        drawer_parts.append(f"<p><strong>Aromatherapy:</strong> {ing.aromatherapy_uses}</p>")
        fields['aromatherapy'] = f"<p>{ing.aromatherapy_uses}</p>"

    # Scent profile
    if ing.scent:
        drawer_parts.append(f"<p><strong>Scent:</strong> {ing.scent}</p>")
        fields['scent'] = f"<p>{ing.scent}</p>"

    # Build the WHAT IT DOES drawer rich text
    if drawer_parts:
        fields['what-it-does'] = ''.join(drawer_parts)

    return fields


def build_who_its_for(ing: IngredientData, cosing: Dict) -> str:
    """
    WHO IT'S FOR drawer - Suitability and safety.
    Uses: skin types, concerns, EWG score, CIR safety, allergy concerns, contraindications
    """
    parts = []

    # Skin types from CosIng
    suitable_for = cosing.get('suitable_for', '')
    if suitable_for:
        parts.append(f"<p><strong>Best For:</strong> {suitable_for}</p>")

    # Skin concerns addressed
    skin_concerns = cosing.get('skin_concerns', '')
    if skin_concerns:
        parts.append(f"<p><strong>Addresses:</strong> {skin_concerns}</p>")

    # EWG Score - from database
    if ing.ewg_score is not None:
        if ing.ewg_score <= 2:
            ewg_label = "Low Hazard"
            ewg_color = "green"
        elif ing.ewg_score <= 6:
            ewg_label = "Moderate"
            ewg_color = "orange"
        else:
            ewg_label = "High Concern"
            ewg_color = "red"
        parts.append(f"<p><strong>EWG Score:</strong> {ing.ewg_score}/10 ({ewg_label})</p>")

    # CIR Safety - from database
    if ing.cir_safety:
        parts.append(f"<p><strong>CIR Assessment:</strong> {ing.cir_safety}</p>")
        if ing.cir_conditions:
            parts.append(f"<p><strong>CIR Conditions:</strong> {ing.cir_conditions}</p>")

    # Health concerns from EWG
    concerns = []
    if ing.cancer_concern and ing.cancer_concern.lower() not in ('none', 'low', ''):
        concerns.append(f"Cancer: {ing.cancer_concern}")
    if ing.allergy_concern and ing.allergy_concern.lower() not in ('none', 'low', ''):
        concerns.append(f"Allergy: {ing.allergy_concern}")
    if ing.developmental_concern and ing.developmental_concern.lower() not in ('none', 'low', ''):
        concerns.append(f"Developmental: {ing.developmental_concern}")

    if concerns:
        parts.append(f"<p><strong>Health Concerns:</strong> {'; '.join(concerns)}</p>")

    # Sensitive skin from CosIng
    sensitive_safe = cosing.get('sensitive_safe', '')
    if sensitive_safe == 'Yes':
        parts.append("<p><strong>Sensitive Skin:</strong> Generally safe</p>")
    elif sensitive_safe == 'No':
        parts.append("<p><strong>Sensitive Skin:</strong> May cause irritation - check restrictions</p>")

    # EU Regulatory status
    eu_annexes = cosing.get('eu_annexes', '')
    if eu_annexes:
        annex_notes = []
        if 'II' in eu_annexes:
            annex_notes.append("Prohibited in EU cosmetics")
        if 'III' in eu_annexes:
            annex_notes.append("Restricted - concentration limits apply")
        if 'IV' in eu_annexes:
            annex_notes.append("Colorant with restrictions")
        if 'V' in eu_annexes:
            annex_notes.append("Preservative with restrictions")
        if 'VI' in eu_annexes:
            annex_notes.append("UV filter with restrictions")
        if annex_notes:
            parts.append(f"<p><strong>EU Status:</strong> {'; '.join(annex_notes)}</p>")

    # Max concentrations
    max_general = cosing.get('max_general_pct', '')
    max_professional = cosing.get('max_professional_pct', '')
    if max_general or max_professional:
        conc_parts = []
        if max_general:
            conc_parts.append(f"General: max {max_general}%")
        if max_professional:
            conc_parts.append(f"Professional: max {max_professional}%")
        parts.append(f"<p><strong>Max Concentration:</strong> {' | '.join(conc_parts)}</p>")

    # Usage conditions/warnings
    usage_conditions = cosing.get('usage_conditions', '')
    if usage_conditions:
        cond = usage_conditions.strip()[:400]
        if len(cond) == 400:
            cond += "..."
        parts.append(f"<p><strong>Usage Conditions:</strong> {cond}</p>")

    # Contraindications from database
    if ing.contraindications:
        parts.append(f"<p><strong>Contraindications:</strong> {ing.contraindications}</p>")

    return ''.join(parts)


def build_how_we_know(ing: IngredientData, cosing: Dict, dirty_lists: list = None) -> str:
    """
    HOW WE KNOW drawer - References and sources.
    Uses: EWG URL, CIR URL, PubChem CID, CosIng ID, SCCS opinions, dirty lists
    """
    parts = []

    # EWG Reference
    if ing.ewg_url:
        parts.append(f'<p><strong>EWG Skin Deep:</strong> <a href="{ing.ewg_url}" target="_blank">View EWG Report</a></p>')
    elif ing.ewg_score is not None:
        parts.append(f"<p><strong>EWG Skin Deep:</strong> Score {ing.ewg_score}/10 (Data availability: {ing.ewg_data_availability or 'Unknown'})</p>")

    # CIR Reference
    if ing.cir_url:
        parts.append(f'<p><strong>CIR Report:</strong> <a href="{ing.cir_url}" target="_blank">View CIR Assessment</a></p>')
    elif ing.cir_safety:
        year_note = f" ({ing.cir_year})" if ing.cir_year else ""
        parts.append(f"<p><strong>CIR Assessment:</strong> {ing.cir_safety}{year_note}</p>")

    # PubChem Reference
    if ing.pubchem_cid:
        pubchem_url = f"https://pubchem.ncbi.nlm.nih.gov/compound/{ing.pubchem_cid}"
        parts.append(f'<p><strong>PubChem:</strong> <a href="{pubchem_url}" target="_blank">Compound {ing.pubchem_cid}</a></p>')

    # CosIng Reference
    cosing_id = ing.cosing_id or cosing.get('cosing_id', '')
    if cosing_id:
        parts.append(f"<p><strong>EU CosIng:</strong> Reference #{cosing_id}</p>")
        parts.append('<p><a href="https://ec.europa.eu/growth/tools-databases/cosing/" target="_blank">EU CosIng Database</a></p>')

    # SCCS Opinions
    sccs = cosing.get('sccs_opinions', '')
    if sccs:
        opinions = sccs.split(' | ')[:3]
        parts.append("<p><strong>SCCS Opinions:</strong></p><ul>")
        for op in opinions:
            if op:
                parts.append(f"<li>{op[:150]}{'...' if len(op) > 150 else ''}</li>")
        parts.append("</ul>")

    # CAS number for further research
    cas = ing.cas_number or cosing.get('cas_no', '')
    if cas and '/' not in cas:  # Single CAS
        parts.append(f'<p><strong>Research:</strong> <a href="https://pubchem.ncbi.nlm.nih.gov/#query={cas}" target="_blank">Search PubChem for {cas}</a></p>')

    # Dirty Lists — Regulatory & Retailer flags
    if dirty_lists:
        status_labels = {
            'prohibited': 'Prohibited',
            'restricted': 'Restricted',
            'excluded': 'Excluded',
            'flagged': 'Flagged',
        }
        parts.append(f"<p><strong>Regulatory &amp; Retailer Lists ({len(dirty_lists)} of 8):</strong></p><ul>")
        for dl in dirty_lists:
            display = dl.get('list_display', dl.get('list', ''))
            status = status_labels.get(dl.get('status', ''), dl.get('status', ''))
            reason = dl.get('reason', '')
            url = dl.get('url', '')
            label = f"{display} — {status}"
            if reason:
                label += f" ({reason})"
            if url:
                parts.append(f'<li><a href="{url}" target="_blank">{label}</a></li>')
            else:
                parts.append(f"<li>{label}</li>")
        parts.append("</ul>")

    return ''.join(parts)


# ============================================================================
# WEBFLOW UPDATER
# ============================================================================

class ComprehensiveDrawerUpdater:
    """Updates all Webflow drawer fields using all available data."""

    def __init__(self):
        self.api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
        self.collection_id = os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        })

        self._last_request = 0
        self.db = IngredientDatabase()
        self.cosing_data = load_cosing_data()
        print(f"Loaded {len(self.cosing_data)} CosIng records")

        # Load dirty lists from unified_ingredients.json
        self.dirty_lists_index = self._load_dirty_lists_index()

    def _load_dirty_lists_index(self) -> Dict[str, List]:
        """Load dirty_lists from unified_ingredients.json, indexed by lowercase INCI name."""
        unified_path = Path(__file__).parent.parent / "data" / "unified_ingredients.json"
        if not unified_path.exists():
            print("Warning: unified_ingredients.json not found for dirty lists")
            return {}
        try:
            with open(unified_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            index = {}
            for item in data:
                dl = item.get("dirty_lists", [])
                if dl:
                    name = (item.get("name") or "").lower().strip()
                    if name:
                        index[name] = dl
                    inci = (item.get("inci_name") or "").lower().strip()
                    if inci and inci != name:
                        index[inci] = dl
            print(f"Loaded dirty lists for {len(index)} ingredients")
            return index
        except Exception as e:
            print(f"Warning: Could not load dirty lists: {e}")
            return {}

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_request = time.time()

    def _request(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        self._rate_limit()
        url = f'{WEBFLOW_API_BASE}{endpoint}'

        try:
            if method == 'PATCH':
                resp = self.session.patch(url, json=data)
            else:
                resp = self.session.get(url)

            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 60))
                print(f'Rate limited. Waiting {wait}s...')
                time.sleep(wait)
                return self._request(method, endpoint, data)

            if not resp.ok:
                print(f'API Error {resp.status_code}: {resp.text[:200]}')
                return None

            return resp.json() if resp.text else {}
        except requests.RequestException as e:
            print(f'Request error: {e}')
            return None

    def update_item(self, item_id: str, fields: Dict) -> bool:
        data = {'fieldData': fields}
        result = self._request('PATCH', f'/collections/{self.collection_id}/items/{item_id}', data)
        return result is not None

    def build_all_fields(self, ing: IngredientData) -> Dict:
        """Build ALL drawer fields from database + CosIng data."""
        cosing = self.cosing_data.get(ing.inci_name.lower(), {})
        fields = {}

        # DRAWER 1: What It Is (IDENTITY ONLY - no descriptions/functions)
        what_it_is = build_what_it_is(ing, cosing)
        if what_it_is:
            fields['what-it-is-common-name-inci-akas-type-form-plant-family-cas-ec-origin-brief-description'] = what_it_is

        # DRAWER 2: What It Does (FUNCTIONS - moved from What It Is)
        what_does = build_what_it_does(ing, cosing)
        fields.update(what_does)

        # DRAWER 3: How It's Made
        how_made = build_how_its_made(ing, cosing)
        if how_made:
            fields['how-it-s-made'] = how_made

        # DRAWER 4: Who It's For
        who_for = build_who_its_for(ing, cosing)
        if who_for:
            fields['who-it-s-for-skin-types-safety-approvals-safety-warnings-safety-contraindications'] = who_for

        # DRAWER 5: How We Know (includes dirty lists)
        dirty_lists = self.dirty_lists_index.get(ing.inci_name.lower(), [])
        how_know = build_how_we_know(ing, cosing, dirty_lists=dirty_lists)
        if how_know:
            fields['how-we-know-references-mla-citations'] = how_know

        # Additional fields
        ing_type = infer_type(ing, cosing)
        fields['type-i-e-mineral-vitamin-botanical-synthetic-plant-derived-synthetic'] = ing_type.lower()

        form = infer_form(ing)
        if form:
            fields['form-3'] = form.lower()

        # CAS/EC
        if ing.cas_number or cosing.get('cas_no'):
            fields['cas-2'] = ing.cas_number or cosing.get('cas_no', '')
        if ing.ec_number:
            fields['ec-2'] = ing.ec_number

        # Plant info
        if ing.plant_part:
            fields['plant-part'] = ing.plant_part
        if ing.origin:
            fields['origin-2'] = ing.origin

        return fields

    def update_all(self, limit: int = None):
        """Update all ingredients with comprehensive drawer content."""
        ingredients = self.db.get_all(limit=limit)

        stats = {
            'total': len(ingredients),
            'updated': 0,
            'failed': 0,
            'skipped_no_webflow_id': 0,
        }

        print(f"Updating {len(ingredients)} ingredients with comprehensive drawer content...")

        for i, ing in enumerate(ingredients):
            if not ing.webflow_id:
                stats['skipped_no_webflow_id'] += 1
                continue

            # Build all fields
            fields = self.build_all_fields(ing)

            if not fields:
                continue

            # Update Webflow
            if self.update_item(ing.webflow_id, fields):
                stats['updated'] += 1
                if (i + 1) % 10 == 0:
                    print(f"  [{i+1}/{len(ingredients)}] Updated: {ing.inci_name[:40]}")
            else:
                stats['failed'] += 1
                print(f"  Failed: {ing.inci_name}")

        print(f"\n{'='*50}")
        print("COMPREHENSIVE DRAWER UPDATE COMPLETE")
        print('='*50)
        print(f"Total: {stats['total']}")
        print(f"Updated: {stats['updated']}")
        print(f"Failed: {stats['failed']}")
        print(f"Skipped (no Webflow ID): {stats['skipped_no_webflow_id']}")

        return stats


def main():
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    updater = ComprehensiveDrawerUpdater()
    updater.update_all(limit=limit)


if __name__ == '__main__':
    main()
