"""
Webflow CMS Sync for Ingredients Collection

Syncs ingredient data from local SQLite database to Webflow CMS.
"""

import os
import time
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

# Load .env file from pipeline directory
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    raise

from .models import IngredientData
from .database import IngredientDatabase


# Webflow API
WEBFLOW_API_BASE = "https://api.webflow.com/v2"


class WebflowIngredientSync:
    """Syncs ingredients to Webflow CMS."""

    def __init__(
        self,
        api_token: str = None,
        site_id: str = None,
        collection_id: str = None,
        db: IngredientDatabase = None
    ):
        """
        Initialize sync client.

        Args:
            api_token: Webflow API token (or WEBFLOW_API_TOKEN env var)
            site_id: Webflow site ID (or WEBFLOW_SITE_ID env var)
            collection_id: Ingredients collection ID (or WEBFLOW_INGREDIENTS_COLLECTION_ID env var)
            db: Ingredient database instance
        """
        self.api_token = api_token or os.environ.get('WEBFLOW_API_TOKEN', '')
        self.site_id = site_id or os.environ.get('WEBFLOW_SITE_ID', '')
        self.collection_id = collection_id or os.environ.get('WEBFLOW_INGREDIENTS_COLLECTION_ID', '')

        if not self.api_token:
            print("Warning: No WEBFLOW_API_TOKEN set")
        if not self.collection_id:
            print("Warning: No WEBFLOW_INGREDIENTS_COLLECTION_ID set")

        self.db = db or IngredientDatabase()

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

        self._rate_limit_remaining = 60
        self._last_request = 0

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request
        if elapsed < 0.5:  # Min 500ms between requests
            time.sleep(0.5 - elapsed)
        self._last_request = time.time()

    def _request(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """Make API request with error handling."""
        self._rate_limit()

        url = f'{WEBFLOW_API_BASE}{endpoint}'

        try:
            if method == 'GET':
                resp = self.session.get(url)
            elif method == 'POST':
                resp = self.session.post(url, json=data)
            elif method == 'PATCH':
                resp = self.session.patch(url, json=data)
            else:
                raise ValueError(f'Unknown method: {method}')

            # Update rate limit
            self._rate_limit_remaining = int(resp.headers.get('X-RateLimit-Remaining', 60))

            # Handle rate limit
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

    def ingredient_to_webflow_fields(self, ingredient: IngredientData) -> Dict:
        """
        Convert IngredientData to Webflow field format.

        Webflow INGREDIENTs Collection Schema:
        - name (PlainText, required): Common/display name
        - slug (PlainText, required): URL-safe identifier
        - inci (RichText): Official INCI name (italics)
        - also-known-as (RichText): Alternative names
        - plant-family (RichText): Botanical family (italics)
        - kind (Option): Ingredient type

        5 Drawer Fields (Rich Text):
        - what-it-is: Common Name, INCI, AKAs, Type, Form, Plant Family, CAS#, EC#, Origin, Description
        - how-its-made: Chemistry, Nutrients, Process
        - what-it-does: Features, Benefits, Functions, Applications, Medicinal, Aromatherapy, Scent
        - who-its-for: Skin Types, Safety Approvals, Warnings, Contraindications
        - how-we-know: References, Citations

        9S Category Fields:
        - stars-attributes, stars-details
        - source-attributes, source-details
        - safety-attributes, safety-details
        - support-attributes, support-details
        - suitability-attributes, suitability-details
        - structure-attributes, structure-details
        - substance-attributes, substance-details
        - sustainability-attributes, sustainability-details

        Persona Scores (Number 0-100):
        - gentle-score, skeptic-score, family-score
        - antiaging-professional-score, genz-score, inclusive-score
        """
        fields = {
            'name': ingredient.common_names[0] if ingredient.common_names else ingredient.inci_name,
            'slug': ingredient.slug,
        }

        # INCI name (rich text for italics)
        fields['inci'] = f"<p><em>{ingredient.inci_name}</em></p>"

        # Also known as / common names
        if ingredient.common_names:
            names_html = ', '.join(ingredient.common_names)
            fields['also-known-as'] = f"<p>{names_html}</p>"

        # Plant family (rich text for italics)
        if ingredient.plant_family:
            fields['plant-family'] = f"<p><em>{ingredient.plant_family}</em></p>"

        # Kind (dropdown) - Option field with limited values
        # Valid options: makeup, skincare, ingredient (must use option IDs)
        # Default to "ingredient" for all items
        fields['kind'] = 'a5b5add476334779101adc95265123e5'  # "ingredient" option ID

        # Type (PlainText) - The actual ingredient type (mineral, vitamin, botanical, synthetic, plant-derived)
        # Infer from ingredient properties
        name_lower = ingredient.inci_name.lower()
        func_lower = (ingredient.function or '').lower()

        # Determine ingredient type based on properties and name
        if ingredient.plant_family or ingredient.plant_part:
            ing_type = "botanical"
        elif any(x in name_lower for x in ['vitamin ', 'retinol', 'tocopherol', 'ascorb', 'niacin', 'panthen', 'biotin', 'folic']):
            ing_type = "vitamin"
        elif any(x in name_lower for x in ['mica', 'silica', 'zinc oxide', 'iron oxide', 'titanium dioxide', 'clay', 'kaolin', 'talc', 'magnesium']):
            ing_type = "mineral"
        elif any(x in name_lower for x in ['ferment', 'lactobacillus', 'saccharomyces', 'bifida', 'probiotic']):
            ing_type = "fermented"
        elif any(x in name_lower for x in [' oil', 'seed oil', 'fruit oil', 'kernel oil', 'butter', ' wax', ' extract', 'flower water', 'leaf ', 'root ', 'bark ', 'fruit ', 'seed ']):
            ing_type = "plant-derived"
        elif any(x in name_lower for x in ['aqua', 'water']):
            ing_type = "mineral"  # Water is mineral-based
        elif any(x in name_lower for x in ['glycerin', 'glycerol', 'propanediol', 'butylene glycol', 'pentylene glycol']):
            ing_type = "plant-derived-synthetic"  # Can be either
        elif any(x in name_lower for x in ['acid', 'alcohol', 'amine', 'polymer', 'acrylate', 'dimethicone', 'silicone', 'peg-', 'ppg-']):
            ing_type = "synthetic"
        else:
            ing_type = "synthetic"  # Default for chemical compounds

        fields['type-i-e-mineral-vitamin-botanical-synthetic-plant-derived-synthetic'] = ing_type

        # ===== 4 DRAWER FIELDS (Rich Text) - using actual Webflow slugs =====

        # DRAWER 1: WHAT IT IS
        what_it_is_parts = []
        if ingredient.common_names:
            what_it_is_parts.append(f"<p><strong>Common Name:</strong> {', '.join(ingredient.common_names)}</p>")
        what_it_is_parts.append(f"<p><strong>INCI:</strong> <em>{ingredient.inci_name}</em></p>")
        if ingredient.kind:
            what_it_is_parts.append(f"<p><strong>Type:</strong> {ingredient.kind}</p>")
        if ingredient.form:
            what_it_is_parts.append(f"<p><strong>Form:</strong> {ingredient.form}</p>")
        if ingredient.plant_family:
            what_it_is_parts.append(f"<p><strong>Plant Family:</strong> <em>{ingredient.plant_family}</em></p>")
        if ingredient.plant_part:
            what_it_is_parts.append(f"<p><strong>Plant Part:</strong> {ingredient.plant_part}</p>")
        if ingredient.cas_number:
            what_it_is_parts.append(f"<p><strong>CAS#:</strong> {ingredient.cas_number}</p>")
        if ingredient.ec_number:
            what_it_is_parts.append(f"<p><strong>EC#:</strong> {ingredient.ec_number}</p>")
        if ingredient.origin:
            what_it_is_parts.append(f"<p><strong>Origin:</strong> {ingredient.origin}</p>")
        if ingredient.description:
            what_it_is_parts.append(f"<p><strong>Description:</strong> {ingredient.description}</p>")
        if what_it_is_parts:
            fields['what-it-is-common-name-inci-akas-type-form-plant-family-cas-ec-origin-brief-description'] = ''.join(what_it_is_parts)

        # DRAWER 2: HOW IT'S MADE
        how_made_parts = []
        if ingredient.molecular_formula:
            how_made_parts.append(f"<p><strong>Molecular Formula:</strong> {ingredient.molecular_formula}</p>")
        if ingredient.molecular_weight:
            how_made_parts.append(f"<p><strong>Molecular Weight:</strong> {ingredient.molecular_weight:.2f} g/mol</p>")
        if ingredient.chemistry_nutrients:
            how_made_parts.append(f"<p><strong>Chemistry/Nutrients:</strong> {ingredient.chemistry_nutrients}</p>")
        if ingredient.process:
            how_made_parts.append(f"<p><strong>Process:</strong> {ingredient.process}</p>")
        if how_made_parts:
            fields['how-it-s-made'] = ''.join(how_made_parts)

        # DRAWER 3: WHAT IT DOES - uses individual fields (no consolidated drawer field)
        # Populate the individual fields instead
        if ingredient.function:
            fields['functions-3'] = ingredient.function
        if ingredient.medicinal_uses:
            fields['medicine'] = f"<p>{ingredient.medicinal_uses}</p>"
        if ingredient.aromatherapy_uses:
            fields['aromatherapy'] = f"<p>{ingredient.aromatherapy_uses}</p>"
        if ingredient.scent:
            fields['scent'] = f"<p>{ingredient.scent}</p>"

        # DRAWER 4: WHO IT'S FOR
        who_its_for_parts = []
        # Skin types based on properties
        skin_types = []
        if ingredient.ewg_score is not None and ingredient.ewg_score <= 2:
            skin_types.append("Sensitive Skin")
        if ingredient.allergy_concern in ('None', 'Low', None):
            skin_types.append("All Skin Types")
        if skin_types:
            who_its_for_parts.append(f"<p><strong>Skin Types:</strong> {', '.join(skin_types)}</p>")

        # Safety approvals
        safety_approvals = []
        if ingredient.cir_safety and 'safe' in ingredient.cir_safety.lower():
            safety_approvals.append(f"CIR: {ingredient.cir_safety}")
        if ingredient.ewg_score is not None and ingredient.ewg_score <= 2:
            safety_approvals.append(f"EWG Score: {ingredient.ewg_score} (Low Hazard)")
        if safety_approvals:
            who_its_for_parts.append(f"<p><strong>Safety Approvals:</strong> {'; '.join(safety_approvals)}</p>")

        # Safety warnings
        safety_warnings = []
        if ingredient.ewg_score is not None and ingredient.ewg_score >= 7:
            safety_warnings.append(f"EWG High Concern (Score: {ingredient.ewg_score})")
        if ingredient.cancer_concern and ingredient.cancer_concern not in ('None', 'Low'):
            safety_warnings.append(f"Cancer concern: {ingredient.cancer_concern}")
        if ingredient.allergy_concern and ingredient.allergy_concern not in ('None', 'Low'):
            safety_warnings.append(f"Allergy concern: {ingredient.allergy_concern}")
        if ingredient.developmental_concern and ingredient.developmental_concern not in ('None', 'Low'):
            safety_warnings.append(f"Developmental concern: {ingredient.developmental_concern}")
        if safety_warnings:
            who_its_for_parts.append(f"<p><strong>Safety Warnings:</strong> {'; '.join(safety_warnings)}</p>")

        # Contraindications
        if ingredient.contraindications:
            who_its_for_parts.append(f"<p><strong>Contraindications:</strong> {ingredient.contraindications}</p>")
        if ingredient.cir_conditions:
            who_its_for_parts.append(f"<p><strong>Usage Conditions:</strong> {ingredient.cir_conditions}</p>")

        if who_its_for_parts:
            fields['who-it-s-for-skin-types-safety-approvals-safety-warnings-safety-contraindications'] = ''.join(who_its_for_parts)

        # DRAWER 5: HOW WE KNOW
        how_we_know_parts = []
        if ingredient.ewg_url:
            how_we_know_parts.append(f"<p><strong>EWG Skin Deep:</strong> <a href=\"{ingredient.ewg_url}\">{ingredient.ewg_url}</a></p>")
        if ingredient.cir_url:
            how_we_know_parts.append(f"<p><strong>CIR Report:</strong> <a href=\"{ingredient.cir_url}\">{ingredient.cir_url}</a></p>")
        if ingredient.pubchem_cid:
            pubchem_url = f"https://pubchem.ncbi.nlm.nih.gov/compound/{ingredient.pubchem_cid}"
            how_we_know_parts.append(f"<p><strong>PubChem:</strong> <a href=\"{pubchem_url}\">{pubchem_url}</a></p>")
        if how_we_know_parts:
            fields['how-we-know-references-mla-citations'] = ''.join(how_we_know_parts)

        # Also populate individual fields that exist
        # Form - infer if not set
        if ingredient.form:
            fields['form-3'] = ingredient.form
        else:
            # Infer form from ingredient name
            name_lower = ingredient.inci_name.lower()
            if any(x in name_lower for x in [' oil', 'seed oil', 'kernel oil', 'fruit oil']):
                form = "oil"
            elif any(x in name_lower for x in [' butter', 'shea butter', 'cocoa butter']):
                form = "butter"
            elif any(x in name_lower for x in [' wax', 'beeswax', 'candelilla']):
                form = "wax"
            elif any(x in name_lower for x in [' powder', 'mica', 'talc', 'silica', 'kaolin', 'clay']):
                form = "powder"
            elif any(x in name_lower for x in [' extract', 'leaf extract', 'root extract', 'flower extract']):
                form = "extract"
            elif any(x in name_lower for x in ['water', 'aqua', 'hydrosol', 'flower water']):
                form = "liquid"
            elif any(x in name_lower for x in ['essential oil']):
                form = "essential oil"
            elif any(x in name_lower for x in ['glycerin', 'glycerol', 'propanediol', 'alcohol']):
                form = "liquid"
            elif any(x in name_lower for x in ['acid']):
                form = "powder"  # Most acids come as powder
            elif any(x in name_lower for x in ['dimethicone', 'silicone', 'cyclomethicone']):
                form = "liquid"
            elif any(x in name_lower for x in ['oxide', 'dioxide']):
                form = "powder"
            else:
                form = None  # Don't set if we can't determine

            if form:
                fields['form-3'] = form

        if ingredient.origin:
            fields['origin-2'] = ingredient.origin
        if ingredient.cas_number:
            fields['cas-2'] = ingredient.cas_number
        if ingredient.ec_number:
            fields['ec-2'] = ingredient.ec_number
        if ingredient.plant_part:
            fields['plant-part'] = ingredient.plant_part

        # ===== PERSONA SCORES =====
        if ingredient.persona_gentle is None:
            ingredient.compute_persona_scores()

        if ingredient.persona_gentle is not None:
            fields['gentle-score'] = ingredient.persona_gentle
        if ingredient.persona_skeptic is not None:
            fields['skeptic-score'] = ingredient.persona_skeptic
        if ingredient.persona_family is not None:
            fields['family-score'] = ingredient.persona_family
        if ingredient.persona_antiaging is not None:
            fields['antiaging-professional-score'] = ingredient.persona_antiaging
        if ingredient.persona_genz is not None:
            fields['genz-score'] = ingredient.persona_genz
        if ingredient.persona_inclusive is not None:
            fields['inclusive-score'] = ingredient.persona_inclusive

        # ===== 9S CATEGORY FIELDS =====

        # STARS - Clinical studies, scientific backing, trending, star rating
        stars_attrs = []
        stars_details = []
        if ingredient.cir_safety:
            stars_attrs.append("scientific-backing")
            stars_details.append(f"CIR reviewed: {ingredient.cir_safety}")
        if ingredient.ewg_data_availability == "Robust":
            stars_attrs.append("clinical-studies")
            stars_details.append("Robust scientific data available")
        # Star rating based on overall safety profile
        if ingredient.ewg_score is not None:
            if ingredient.ewg_score <= 2:
                stars_attrs.append("5-out-of-5")
            elif ingredient.ewg_score <= 4:
                stars_attrs.append("4-out-of-5")
            elif ingredient.ewg_score <= 6:
                stars_attrs.append("3-out-of-5")
            elif ingredient.ewg_score <= 8:
                stars_attrs.append("2-out-of-5")
            else:
                stars_attrs.append("1-out-of-5")
        if stars_attrs:
            fields['stars-attributes'] = ', '.join(stars_attrs)
        if stars_details:
            fields['stars-details'] = ' | '.join(stars_details)

        # SOURCE - Plant-derived, synthetic, fermented, mineral, marine, country of origin
        source_attrs = []
        source_details = []
        if ingredient.plant_family or ingredient.plant_part:
            source_attrs.append("plant-derived")
            if ingredient.plant_family:
                source_details.append(f"Plant family: {ingredient.plant_family}")
            if ingredient.plant_part:
                source_details.append(f"Plant part: {ingredient.plant_part}")
        if ingredient.origin:
            source_attrs.append("country-of-origin")
            source_details.append(f"Origin: {ingredient.origin}")
        # Infer source type from name/function
        name_lower = ingredient.inci_name.lower()
        func_lower = (ingredient.function or '').lower()
        if any(x in name_lower for x in ['ferment', 'lactobacillus', 'saccharomyces']):
            source_attrs.append("fermented")
        if any(x in name_lower for x in ['mica', 'silica', 'zinc', 'iron oxide', 'titanium']):
            source_attrs.append("mineral")
        if any(x in name_lower for x in ['algae', 'seaweed', 'kelp', 'marine', 'sea']):
            source_attrs.append("marine")
        if not ingredient.plant_family and not any(x in source_attrs for x in ['fermented', 'mineral', 'marine']):
            if any(x in func_lower for x in ['synthetic', 'petroleum']):
                source_attrs.append("synthetic")
        if source_attrs:
            fields['source-attributes'] = ', '.join(source_attrs)
        if source_details:
            fields['source-details'] = ' | '.join(source_details)

        # SAFETY - EWG ratings (all), pregnancy/nursing safe, medical approval, certifications, allergens, warnings
        safety_attrs = []
        safety_details = []

        # EWG rating (always include the actual rating)
        if ingredient.ewg_score is not None:
            safety_attrs.append(f"ewg-{ingredient.ewg_score}")
            if ingredient.ewg_score <= 2:
                safety_details.append(f"EWG Score: {ingredient.ewg_score} (Low Hazard)")
            elif ingredient.ewg_score <= 6:
                safety_details.append(f"EWG Score: {ingredient.ewg_score} (Moderate)")
            else:
                safety_details.append(f"EWG Score: {ingredient.ewg_score} (High Concern)")

        # CIR safety
        if ingredient.cir_safety:
            if 'safe as used' in ingredient.cir_safety.lower():
                safety_attrs.append("medical-approval")
                safety_attrs.append("safety-certifications")
            safety_details.append(f"CIR: {ingredient.cir_safety}")

        # Pregnancy/nursing safe (infer from low concern levels)
        if (ingredient.ewg_score is not None and ingredient.ewg_score <= 2 and
            ingredient.developmental_concern in ('None', 'Low', None)):
            safety_attrs.append("pregnancy-nursing-safe")
            safety_attrs.append("nursing-safe")

        # All shades safe (no skin sensitization concerns)
        if ingredient.allergy_concern in ('None', 'Low', None):
            safety_attrs.append("all-shades-safe")
        else:
            safety_details.append(f"Allergy concern: {ingredient.allergy_concern}")

        # Cancer concern
        if ingredient.cancer_concern and ingredient.cancer_concern not in ('None', 'Low'):
            safety_details.append(f"Cancer concern: {ingredient.cancer_concern}")

        # Check for specific warnings in contraindications
        contra_lower = (ingredient.contraindications or '').lower()
        if 'epilep' in contra_lower or 'seizure' in contra_lower:
            safety_attrs.append("avoid-if-epileptic")
        if 'pet' in contra_lower or 'cat' in contra_lower or 'dog' in contra_lower:
            safety_attrs.append("avoid-around-pets")
        if 'photosensi' in contra_lower or 'sun' in contra_lower:
            safety_attrs.append("photosensitizing")

        if safety_attrs:
            fields['safety-attributes'] = ', '.join(safety_attrs)
        if safety_details:
            fields['safety-details'] = ' | '.join(safety_details)

        # SUPPORT - Benefits: moisturizing, anti-aging, brightening, soothing, exfoliating, protecting, etc.
        support_attrs = []
        support_details = []
        func_lower = (ingredient.function or '').lower()
        med_lower = (ingredient.medicinal_uses or '').lower()
        combined = func_lower + ' ' + med_lower

        if any(x in combined for x in ['moistur', 'hydrat', 'humectant', 'emollient']):
            support_attrs.append("moisturizing")
        if any(x in combined for x in ['anti-aging', 'antiaging', 'wrinkle', 'firm']):
            support_attrs.append("antiaging")
        if any(x in combined for x in ['brighten', 'lighten', 'radian']):
            support_attrs.append("brightening")
        if any(x in combined for x in ['sooth', 'calm', 'anti-inflam']):
            support_attrs.append("soothing")
        if any(x in combined for x in ['exfolia', 'peel', 'aha', 'bha']):
            support_attrs.append("exfoliating")
        if any(x in combined for x in ['protect', 'barrier', 'shield']):
            support_attrs.append("nourishing-protecting")
        if any(x in combined for x in ['oil control', 'mattif', 'sebum']):
            support_attrs.append("oil-control")
        if any(x in combined for x in ['nourish', 'repair', 'heal']):
            support_attrs.append("nourishing-protecting")
        if any(x in combined for x in ['clarif', 'pore', 'acne', 'blemish']):
            support_attrs.append("clarifying")
        if any(x in combined for x in ['blur', 'smooth', 'soft focus']):
            support_attrs.append("camera-ready")

        if ingredient.function:
            support_details.append(f"Function: {ingredient.function}")
        if ingredient.medicinal_uses:
            support_details.append(ingredient.medicinal_uses[:200])

        if support_attrs:
            fields['support-attributes'] = ', '.join(list(set(support_attrs)))  # dedupe
        if support_details:
            fields['support-details'] = ' | '.join(support_details)

        # SUITABILITY - Skin types
        suitability_attrs = []
        suitability_details = []

        # Infer skin type suitability from properties
        if ingredient.ewg_score is not None and ingredient.ewg_score <= 2:
            suitability_attrs.append("gentle")
        if ingredient.allergy_concern in ('None', 'Low', None):
            suitability_attrs.append("all-skin-types")

        # Check function for skin type hints
        func_lower = (ingredient.function or '').lower()
        if any(x in func_lower for x in ['oil control', 'mattif', 'astringent']):
            suitability_attrs.append("skin-types")  # oily skin
            suitability_details.append("Good for oily skin")
        if any(x in func_lower for x in ['emollient', 'moistur', 'hydrat']):
            suitability_attrs.append("skin-types")  # dry skin
            suitability_details.append("Good for dry/dehydrated skin")
        if any(x in func_lower for x in ['sooth', 'calm', 'anti-irrit']):
            suitability_attrs.append("gentle")
            suitability_details.append("Good for sensitive skin")

        if suitability_attrs:
            fields['suitability-attributes'] = ', '.join(list(set(suitability_attrs)))
        if suitability_details:
            fields['suitability-details'] = ' | '.join(suitability_details)

        # STRUCTURE - Form: oil, powder, liquid, wax, extract, solid
        structure_attrs = []
        structure_details = []

        if ingredient.form:
            form_lower = ingredient.form.lower()
            if 'oil' in form_lower:
                structure_attrs.append("format")  # oil
            elif 'powder' in form_lower:
                structure_attrs.append("format")  # powder
            elif 'liquid' in form_lower:
                structure_attrs.append("format")  # liquid
            elif 'wax' in form_lower:
                structure_attrs.append("format")  # wax
            elif 'solid' in form_lower:
                structure_attrs.append("format")  # solid
            structure_details.append(f"Form: {ingredient.form}")

        # Infer from name
        name_lower = ingredient.inci_name.lower()
        if 'extract' in name_lower:
            structure_attrs.append("formulation")  # extract
        if 'oil' in name_lower and 'format' not in structure_attrs:
            structure_attrs.append("format")
        if 'wax' in name_lower and 'format' not in structure_attrs:
            structure_attrs.append("format")

        if ingredient.scent:
            structure_details.append(f"Scent: {ingredient.scent}")

        if structure_attrs:
            fields['structure-attributes'] = ', '.join(list(set(structure_attrs)))
        if structure_details:
            fields['structure-details'] = ' | '.join(structure_details)

        # SUBSTANCE - Type: active, carrier, preservative, fragrance, surfactant, colorant, exfoliant
        substance_attrs = []
        substance_details = []
        func_lower = (ingredient.function or '').lower()

        if 'preservative' in func_lower:
            substance_attrs.append("key-ingredients")
            substance_details.append("Type: Preservative")
        if 'fragrance' in func_lower or 'perfum' in func_lower:
            substance_attrs.append("key-ingredients")
            substance_details.append("Type: Fragrance")
        if 'surfactant' in func_lower:
            substance_attrs.append("base-ingredients")
            substance_details.append("Type: Surfactant")
        if 'colorant' in func_lower or 'color' in func_lower or 'ci ' in func_lower:
            substance_attrs.append("key-ingredients")
            substance_details.append("Type: Colorant")
        if 'exfolia' in func_lower:
            substance_attrs.append("key-ingredients")
            substance_details.append("Type: Exfoliant")
        if any(x in func_lower for x in ['emollient', 'carrier', 'base']):
            substance_attrs.append("base-ingredients")
            substance_details.append("Type: Carrier/Base")
        if any(x in func_lower for x in ['active', 'antioxidant', 'anti-aging']):
            substance_attrs.append("key-ingredients")
            substance_details.append("Type: Active")

        if ingredient.function:
            substance_details.append(f"Function: {ingredient.function}")
        if ingredient.cas_number:
            substance_details.append(f"CAS: {ingredient.cas_number}")

        if substance_attrs:
            fields['substance-attributes'] = ', '.join(list(set(substance_attrs)))
        if substance_details:
            fields['substance-details'] = ' | '.join(substance_details)

        # SUSTAINABILITY - Organic, sustainably sourced, plant-derived, natural
        sustainability_attrs = []
        sustainability_details = []

        if ingredient.plant_family or ingredient.plant_part:
            sustainability_attrs.append("ingredients")  # plant-derived
            sustainability_attrs.append("organic")  # natural
            sustainability_details.append("Plant-derived ingredient")

        # Check name for organic indicators
        name_lower = ingredient.inci_name.lower()
        if 'organic' in name_lower:
            sustainability_attrs.append("organic")
            sustainability_details.append("Certified organic")

        # Synthetic alternative check
        if not ingredient.plant_family and 'synthetic' not in sustainability_attrs:
            if any(x in (ingredient.function or '').lower() for x in ['bio-identical', 'nature-identical']):
                sustainability_attrs.append("manufacturing")  # synthetic alternative
                sustainability_details.append("Nature-identical synthetic")

        if sustainability_attrs:
            fields['sustainability-attributes'] = ', '.join(list(set(sustainability_attrs)))
        if sustainability_details:
            fields['sustainability-details'] = ' | '.join(sustainability_details)

        # ===== IMAGES =====
        # Webflow accepts image URLs as {"url": "https://..."}

        # Hero image (closeup)
        if hasattr(ingredient, 'hero_image_url') and ingredient.hero_image_url:
            fields['hero-image'] = {"url": ingredient.hero_image_url}

        # Molecular structure / in-the-field image
        if hasattr(ingredient, 'structure_image_url') and ingredient.structure_image_url:
            fields['in-the-field-image'] = {"url": ingredient.structure_image_url}

        return fields

    def find_by_slug(self, slug: str) -> Optional[Dict]:
        """Find existing item by slug."""
        result = self._request('GET', f'/collections/{self.collection_id}/items?slug={slug}')
        if result and result.get('items'):
            return result['items'][0]
        return None

    def create_item(self, ingredient: IngredientData) -> Optional[str]:
        """
        Create a new ingredient item in Webflow.
        Returns the item ID or None if failed.
        """
        fields = self.ingredient_to_webflow_fields(ingredient)

        data = {
            'fieldData': fields,
            'isArchived': False,
            'isDraft': False,
        }

        result = self._request('POST', f'/collections/{self.collection_id}/items', data)

        if result and result.get('id'):
            return result['id']
        return None

    def update_item(self, item_id: str, ingredient: IngredientData) -> bool:
        """Update an existing ingredient item."""
        fields = self.ingredient_to_webflow_fields(ingredient)

        data = {
            'fieldData': fields,
        }

        result = self._request('PATCH', f'/collections/{self.collection_id}/items/{item_id}', data)
        return result is not None

    def upsert_item(self, ingredient: IngredientData) -> Optional[str]:
        """
        Create or update ingredient item.
        Returns the item ID.
        """
        # Check if exists
        existing = self.find_by_slug(ingredient.slug)

        if existing:
            item_id = existing.get('id')
            if self.update_item(item_id, ingredient):
                return item_id
            return None
        else:
            return self.create_item(ingredient)

    def sync_ingredient(self, ingredient: IngredientData) -> bool:
        """
        Sync a single ingredient to Webflow and update local DB with Webflow ID.
        Returns True if successful.
        """
        item_id = self.upsert_item(ingredient)

        if item_id:
            # Update local DB with Webflow ID
            self.db.set_webflow_id(ingredient.inci_name, item_id)
            return True

        return False

    def sync_all(self, limit: int = None, progress_callback=None) -> Dict:
        """
        Sync all ingredients from local DB to Webflow.

        Args:
            limit: Max number to sync (None for all)
            progress_callback: Function(current, total, name) for progress updates

        Returns:
            Dict with sync statistics
        """
        # Get ingredients to sync
        if limit:
            ingredients = self.db.get_all(limit=limit)
        else:
            ingredients = self.db.get_all()

        stats = {
            'total': len(ingredients),
            'success': 0,
            'failed': 0,
            'skipped': 0,
        }

        for i, ingredient in enumerate(ingredients):
            if progress_callback:
                progress_callback(i + 1, stats['total'], ingredient.inci_name)

            # Skip if already synced
            if ingredient.webflow_id:
                stats['skipped'] += 1
                continue

            if self.sync_ingredient(ingredient):
                stats['success'] += 1
                print(f'  Synced: {ingredient.inci_name}')
            else:
                stats['failed'] += 1
                print(f'  Failed: {ingredient.inci_name}')

        return stats

    def sync_unsynced(self, limit: int = 100, progress_callback=None) -> Dict:
        """
        Sync only ingredients not yet in Webflow.

        Args:
            limit: Max number to sync per batch
            progress_callback: Progress callback function

        Returns:
            Dict with sync statistics
        """
        ingredients = self.db.get_without_webflow_id(limit=limit)

        stats = {
            'total': len(ingredients),
            'success': 0,
            'failed': 0,
        }

        for i, ingredient in enumerate(ingredients):
            if progress_callback:
                progress_callback(i + 1, stats['total'], ingredient.inci_name)

            if self.sync_ingredient(ingredient):
                stats['success'] += 1
            else:
                stats['failed'] += 1

        return stats

    def get_collection_info(self) -> Optional[Dict]:
        """Get Ingredients collection schema and info."""
        return self._request('GET', f'/collections/{self.collection_id}')

    def list_collections(self) -> List[Dict]:
        """List all collections in the site."""
        result = self._request('GET', f'/sites/{self.site_id}/collections')
        return result.get('collections', []) if result else []

    def find_ingredients_collection(self) -> Optional[str]:
        """
        Find the Ingredients collection by name.
        Returns collection ID if found.
        """
        collections = self.list_collections()
        for col in collections:
            name = col.get('displayName', '').lower()
            slug = col.get('slug', '').lower()
            if 'ingredient' in name or 'ingredient' in slug:
                return col.get('id')
        return None


def sync_to_webflow(limit: int = None, unsynced_only: bool = True) -> Dict:
    """
    Convenience function to sync ingredients to Webflow.

    Args:
        limit: Max ingredients to sync
        unsynced_only: If True, only sync ingredients not yet in Webflow

    Returns:
        Dict with sync statistics
    """
    db = IngredientDatabase()
    sync = WebflowIngredientSync(db=db)

    def progress(current, total, name):
        print(f'[{current}/{total}] {name}')

    if unsynced_only:
        return sync.sync_unsynced(limit=limit or 100, progress_callback=progress)
    else:
        return sync.sync_all(limit=limit, progress_callback=progress)


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--info':
        # Show collection info
        sync = WebflowIngredientSync()
        print('\nLooking for Ingredients collection...')

        collections = sync.list_collections()
        print(f'\nFound {len(collections)} collections:')
        for col in collections:
            print(f"  - {col.get('displayName')}: {col.get('id')}")

        if sync.collection_id:
            print(f'\nIngredients collection info:')
            info = sync.get_collection_info()
            if info:
                print(f"  Name: {info.get('displayName')}")
                print(f"  ID: {info.get('id')}")
                fields = info.get('fields', [])
                print(f"  Fields: {len(fields)}")
                for f in fields:
                    print(f"    - {f.get('slug')}: {f.get('type')}")

    elif len(sys.argv) > 1 and sys.argv[1] == '--sync':
        # Sync ingredients
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        print(f'\nSyncing up to {limit} ingredients...\n')

        stats = sync_to_webflow(limit=limit)

        print(f'\n{"="*40}')
        print('SYNC COMPLETE')
        print('='*40)
        print(f"Total: {stats['total']}")
        print(f"Success: {stats['success']}")
        print(f"Failed: {stats['failed']}")

    else:
        print('Webflow Ingredient Sync')
        print()
        print('Usage:')
        print('  python webflow_sync.py --info     # Show collection info')
        print('  python webflow_sync.py --sync     # Sync 100 ingredients')
        print('  python webflow_sync.py --sync 50  # Sync 50 ingredients')
        print()
        print('Required environment variables:')
        print('  WEBFLOW_API_TOKEN')
        print('  WEBFLOW_SITE_ID')
        print('  WEBFLOW_INGREDIENTS_COLLECTION_ID')
