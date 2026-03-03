"""
Data models for ingredient database system.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class IngredientData:
    """Unified ingredient data from EWG, CIR, CosIng, and PubChem sources."""

    inci_name: str
    slug: str = ""
    common_names: List[str] = field(default_factory=list)

    # EWG Skin Deep data
    ewg_score: Optional[int] = None  # 1-10 scale (1=safest)
    ewg_concern_level: Optional[str] = None  # "Low Hazard", "Moderate Hazard", "High Hazard"
    ewg_data_availability: Optional[str] = None  # "Robust", "Fair", "Limited", "None"
    ewg_url: Optional[str] = None
    ewg_id: Optional[str] = None

    # Health concerns from EWG
    cancer_concern: Optional[str] = None  # "None", "Low", "Moderate", "High"
    developmental_concern: Optional[str] = None
    allergy_concern: Optional[str] = None
    organ_toxicity: Optional[str] = None

    # CIR Safety data
    cir_safety: Optional[str] = None  # "Safe as used", "Safe with qualifications", "Unsafe", "Insufficient data"
    cir_conditions: Optional[str] = None  # Any usage conditions
    cir_url: Optional[str] = None
    cir_id: Optional[str] = None
    cir_year: Optional[int] = None

    # CosIng (EU) data
    cas_number: Optional[str] = None  # CAS Registry Number (e.g., "56-81-5")
    ec_number: Optional[str] = None  # EC/EINECS Number (e.g., "200-289-5")
    cosing_id: Optional[str] = None

    # PubChem data
    pubchem_cid: Optional[int] = None  # PubChem Compound ID
    molecular_formula: Optional[str] = None  # e.g., "C3H8O3"
    molecular_weight: Optional[float] = None  # in g/mol

    # General info
    function: Optional[str] = None  # "Surfactant", "Preservative", "Emollient", etc.
    description: Optional[str] = None
    banned_regions: List[str] = field(default_factory=list)

    # Botanical/natural ingredient data
    plant_family: Optional[str] = None  # e.g., "Lamiaceae" for lavender
    plant_part: Optional[str] = None  # e.g., "Flower", "Seed", "Leaf", "Root"
    origin: Optional[str] = None  # Geographic or source origin
    process: Optional[str] = None  # Extraction/processing method

    # Physical properties
    form: Optional[str] = None  # "Liquid", "Powder", "Wax", "Oil", etc.
    scent: Optional[str] = None  # Scent description

    # Uses and applications
    aromatherapy_uses: Optional[str] = None  # Aromatherapy applications
    medicinal_uses: Optional[str] = None  # Medicinal/therapeutic uses
    chemistry_nutrients: Optional[str] = None  # Combined chemistry/nutrient info

    # Ingredient kind/type
    kind: Optional[str] = None  # "Essential Oil", "Extract", "Butter", "Wax", "Acid", etc.

    # Persona scores (0-100)
    persona_gentle: Optional[int] = None
    persona_skeptic: Optional[int] = None
    persona_family: Optional[int] = None
    persona_antiaging: Optional[int] = None
    persona_genz: Optional[int] = None
    persona_inclusive: Optional[int] = None

    # Safety summary for Webflow
    safety_concerns: Optional[str] = None  # Combined safety concerns text
    contraindications: Optional[str] = None  # Usage warnings

    # Computed flags
    is_clean: bool = False  # EWG 1-2 with no major concerns
    is_controversial: bool = False  # Conflicting safety data

    # Image URLs
    hero_image_url: Optional[str] = None  # Closeup/hero image
    structure_image_url: Optional[str] = None  # Molecular structure image from PubChem

    # Metadata
    webflow_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    ewg_scraped_at: Optional[datetime] = None
    cir_scraped_at: Optional[datetime] = None
    cosing_scraped_at: Optional[datetime] = None
    pubchem_scraped_at: Optional[datetime] = None

    def __post_init__(self):
        """Generate slug from INCI name if not provided."""
        if not self.slug:
            self.slug = self._slugify(self.inci_name)
        self._compute_flags()

    def _slugify(self, name: str) -> str:
        """Convert ingredient name to URL-safe slug."""
        import re
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')[:100]

    def _compute_flags(self):
        """Compute is_clean and is_controversial flags."""
        # Is clean: EWG score 1-2 AND no cancer/developmental concerns
        if self.ewg_score is not None:
            low_ewg = self.ewg_score <= 2
            no_cancer = self.cancer_concern in (None, "None", "Low")
            no_dev = self.developmental_concern in (None, "None", "Low")
            self.is_clean = low_ewg and no_cancer and no_dev

        # Is controversial: conflicting data sources
        if self.ewg_score and self.cir_safety:
            ewg_safe = self.ewg_score <= 3
            cir_unsafe = self.cir_safety in ("Unsafe", "Safe with qualifications")
            ewg_unsafe = self.ewg_score >= 7
            cir_safe = self.cir_safety == "Safe as used"
            self.is_controversial = (ewg_safe and cir_unsafe) or (ewg_unsafe and cir_safe)

    def compute_persona_scores(self):
        """Calculate persona scores based on ingredient safety data."""
        # Start with base score of 50 for each persona
        base_score = 50

        # Gentle persona: sensitive skin focus
        gentle = base_score
        if self.ewg_score:
            if self.ewg_score <= 2:
                gentle += 30
            elif self.ewg_score <= 4:
                gentle += 10
            elif self.ewg_score >= 7:
                gentle -= 30
        if self.allergy_concern and self.allergy_concern.lower() not in ('none', 'low'):
            gentle -= 20
        self.persona_gentle = max(0, min(100, gentle))

        # Skeptic persona: science-backed, CIR verified
        skeptic = base_score
        if self.cir_safety == "Safe as used":
            skeptic += 25
        elif self.cir_safety == "Safe with qualifications":
            skeptic += 10
        elif self.cir_safety == "Insufficient data":
            skeptic -= 15
        if self.ewg_data_availability == "Robust":
            skeptic += 10
        self.persona_skeptic = max(0, min(100, skeptic))

        # Family persona: avoid cancer/developmental concerns
        family = base_score
        if self.cancer_concern and self.cancer_concern.lower() not in ('none', 'low'):
            family -= 35
        if self.developmental_concern and self.developmental_concern.lower() not in ('none', 'low'):
            family -= 25
        if self.ewg_score and self.ewg_score <= 2:
            family += 25
        self.persona_family = max(0, min(100, family))

        # Anti-aging/Professional: efficacy-focused
        antiaging = base_score
        if self.function:
            func_lower = self.function.lower()
            if any(x in func_lower for x in ['antioxidant', 'anti-aging', 'skin conditioning']):
                antiaging += 20
        if self.ewg_score and self.ewg_score <= 4:
            antiaging += 10
        self.persona_antiaging = max(0, min(100, antiaging))

        # GenZ persona: clean + trendy
        genz = base_score
        if self.is_clean:
            genz += 30
        if self.ewg_score and self.ewg_score <= 2:
            genz += 15
        self.persona_genz = max(0, min(100, genz))

        # Inclusive persona: generally safe for all
        inclusive = base_score
        if self.allergy_concern and self.allergy_concern.lower() in ('none', 'low'):
            inclusive += 15
        if self.ewg_score and self.ewg_score <= 3:
            inclusive += 15
        self.persona_inclusive = max(0, min(100, inclusive))

    def generate_safety_concerns_text(self) -> str:
        """Generate combined safety concerns text for Webflow."""
        concerns = []

        if self.ewg_score and self.ewg_score >= 7:
            concerns.append(f"EWG High Hazard (Score: {self.ewg_score}/10)")
        elif self.ewg_score and self.ewg_score >= 4:
            concerns.append(f"EWG Moderate (Score: {self.ewg_score}/10)")

        if self.cancer_concern and self.cancer_concern.lower() not in ('none', 'low', ''):
            concerns.append(f"Cancer concern: {self.cancer_concern}")

        if self.allergy_concern and self.allergy_concern.lower() not in ('none', 'low', ''):
            concerns.append(f"Allergy concern: {self.allergy_concern}")

        if self.developmental_concern and self.developmental_concern.lower() not in ('none', 'low', ''):
            concerns.append(f"Developmental concern: {self.developmental_concern}")

        if self.cir_safety == "Unsafe":
            concerns.append("CIR: Determined unsafe")
        elif self.cir_safety == "Safe with qualifications":
            if self.cir_conditions:
                concerns.append(f"CIR: {self.cir_conditions}")
            else:
                concerns.append("CIR: Safe with restrictions")

        self.safety_concerns = "; ".join(concerns) if concerns else "No major concerns identified"
        return self.safety_concerns

    def infer_kind(self):
        """Infer ingredient kind from name and properties."""
        name_lower = self.inci_name.lower()
        func_lower = (self.function or '').lower()

        if 'essential oil' in name_lower or 'oil' in name_lower:
            if 'essential' in name_lower:
                self.kind = "Essential Oil"
            elif any(x in name_lower for x in ['castor', 'jojoba', 'argan', 'coconut', 'olive']):
                self.kind = "Carrier Oil"
            else:
                self.kind = "Oil"
        elif 'extract' in name_lower:
            self.kind = "Extract"
        elif 'butter' in name_lower:
            self.kind = "Butter"
        elif 'wax' in name_lower:
            self.kind = "Wax"
        elif 'acid' in name_lower:
            self.kind = "Acid"
        elif 'vitamin' in name_lower:
            self.kind = "Vitamin"
        elif any(x in name_lower for x in ['water', 'aqua']):
            self.kind = "Water"
        elif 'fragrance' in func_lower or 'parfum' in name_lower:
            self.kind = "Fragrance"
        elif 'preservative' in func_lower:
            self.kind = "Preservative"
        elif 'surfactant' in func_lower:
            self.kind = "Surfactant"
        elif 'emollient' in func_lower:
            self.kind = "Emollient"
        else:
            self.kind = "Ingredient"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON/database storage."""
        return {
            'inci_name': self.inci_name,
            'slug': self.slug,
            'common_names': ','.join(self.common_names) if self.common_names else '',
            # EWG data
            'ewg_score': self.ewg_score,
            'ewg_concern_level': self.ewg_concern_level,
            'ewg_data_availability': self.ewg_data_availability,
            'ewg_url': self.ewg_url,
            'ewg_id': self.ewg_id,
            'cancer_concern': self.cancer_concern,
            'developmental_concern': self.developmental_concern,
            'allergy_concern': self.allergy_concern,
            'organ_toxicity': self.organ_toxicity,
            # CIR data
            'cir_safety': self.cir_safety,
            'cir_conditions': self.cir_conditions,
            'cir_url': self.cir_url,
            'cir_id': self.cir_id,
            'cir_year': self.cir_year,
            # CosIng data
            'cas_number': self.cas_number,
            'ec_number': self.ec_number,
            'cosing_id': self.cosing_id,
            # PubChem data
            'pubchem_cid': self.pubchem_cid,
            'molecular_formula': self.molecular_formula,
            'molecular_weight': self.molecular_weight,
            # General info
            'function': self.function,
            'description': self.description,
            'banned_regions': ','.join(self.banned_regions) if self.banned_regions else '',
            # Botanical data
            'plant_family': self.plant_family,
            'plant_part': self.plant_part,
            'origin': self.origin,
            'process': self.process,
            # Physical properties
            'form': self.form,
            'scent': self.scent,
            # Uses
            'aromatherapy_uses': self.aromatherapy_uses,
            'medicinal_uses': self.medicinal_uses,
            'chemistry_nutrients': self.chemistry_nutrients,
            # Classification
            'kind': self.kind,
            # Persona scores
            'persona_gentle': self.persona_gentle,
            'persona_skeptic': self.persona_skeptic,
            'persona_family': self.persona_family,
            'persona_antiaging': self.persona_antiaging,
            'persona_genz': self.persona_genz,
            'persona_inclusive': self.persona_inclusive,
            # Safety
            'safety_concerns': self.safety_concerns,
            'contraindications': self.contraindications,
            # Flags
            'is_clean': self.is_clean,
            'is_controversial': self.is_controversial,
            'webflow_id': self.webflow_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'IngredientData':
        """Create instance from dictionary."""
        common_names = data.get('common_names', '')
        if isinstance(common_names, str) and common_names:
            common_names = [n.strip() for n in common_names.split(',')]
        else:
            common_names = common_names if isinstance(common_names, list) else []

        banned_regions = data.get('banned_regions', '')
        if isinstance(banned_regions, str) and banned_regions:
            banned_regions = [r.strip() for r in banned_regions.split(',')]
        else:
            banned_regions = banned_regions if isinstance(banned_regions, list) else []

        return cls(
            inci_name=data.get('inci_name', ''),
            slug=data.get('slug', ''),
            common_names=common_names,
            # EWG data
            ewg_score=data.get('ewg_score'),
            ewg_concern_level=data.get('ewg_concern_level'),
            ewg_data_availability=data.get('ewg_data_availability'),
            ewg_url=data.get('ewg_url'),
            ewg_id=data.get('ewg_id'),
            cancer_concern=data.get('cancer_concern'),
            developmental_concern=data.get('developmental_concern'),
            allergy_concern=data.get('allergy_concern'),
            organ_toxicity=data.get('organ_toxicity'),
            # CIR data
            cir_safety=data.get('cir_safety'),
            cir_conditions=data.get('cir_conditions'),
            cir_url=data.get('cir_url'),
            cir_id=data.get('cir_id'),
            cir_year=data.get('cir_year'),
            # CosIng data
            cas_number=data.get('cas_number'),
            ec_number=data.get('ec_number'),
            cosing_id=data.get('cosing_id'),
            # PubChem data
            pubchem_cid=data.get('pubchem_cid'),
            molecular_formula=data.get('molecular_formula'),
            molecular_weight=data.get('molecular_weight'),
            # General info
            function=data.get('function'),
            description=data.get('description'),
            banned_regions=banned_regions,
            # Botanical data
            plant_family=data.get('plant_family'),
            plant_part=data.get('plant_part'),
            origin=data.get('origin'),
            process=data.get('process'),
            # Physical properties
            form=data.get('form'),
            scent=data.get('scent'),
            # Uses
            aromatherapy_uses=data.get('aromatherapy_uses'),
            medicinal_uses=data.get('medicinal_uses'),
            chemistry_nutrients=data.get('chemistry_nutrients'),
            # Classification
            kind=data.get('kind'),
            # Persona scores
            persona_gentle=data.get('persona_gentle'),
            persona_skeptic=data.get('persona_skeptic'),
            persona_family=data.get('persona_family'),
            persona_antiaging=data.get('persona_antiaging'),
            persona_genz=data.get('persona_genz'),
            persona_inclusive=data.get('persona_inclusive'),
            # Safety
            safety_concerns=data.get('safety_concerns'),
            contraindications=data.get('contraindications'),
            # Flags
            is_clean=data.get('is_clean', False),
            is_controversial=data.get('is_controversial', False),
            # Images
            hero_image_url=data.get('hero_image_url'),
            structure_image_url=data.get('structure_image_url'),
            # Metadata
            webflow_id=data.get('webflow_id'),
        )


@dataclass
class ProductSafetyReport:
    """Safety analysis for a product based on ingredient database lookups."""

    product_slug: str
    product_name: str = ""

    # Counts
    total_ingredients: int = 0
    matched_ingredients: int = 0
    unmatched_ingredients: int = 0

    # Aggregate scores
    average_ewg_score: Optional[float] = None
    max_ewg_score: Optional[int] = None
    min_ewg_score: Optional[int] = None

    # Concern counts
    cancer_concern_count: int = 0
    allergy_concern_count: int = 0
    developmental_concern_count: int = 0

    # CIR stats
    cir_safe_count: int = 0
    cir_qualified_count: int = 0
    cir_unsafe_count: int = 0
    cir_insufficient_count: int = 0

    # Ingredient lists
    clean_ingredients: List[str] = field(default_factory=list)
    concerning_ingredients: List[str] = field(default_factory=list)
    unknown_ingredients: List[str] = field(default_factory=list)
    controversial_ingredients: List[str] = field(default_factory=list)

    # Full ingredient data for detailed reports
    ingredient_details: List[IngredientData] = field(default_factory=list)

    # Persona score modifiers (-30 to +30)
    family_modifier: int = 0
    gentle_modifier: int = 0
    skeptic_modifier: int = 0

    # Summary text for Webflow
    safety_summary: str = ""
    safety_details: str = ""

    def calculate_modifiers(self):
        """Calculate persona score modifiers based on ingredient analysis."""
        # Family modifier: penalize cancer/developmental concerns, reward clean
        if self.cancer_concern_count > 0:
            self.family_modifier -= min(20, self.cancer_concern_count * 10)
        if self.developmental_concern_count > 0:
            self.family_modifier -= min(15, self.developmental_concern_count * 5)
        if self.average_ewg_score:
            if self.average_ewg_score <= 2:
                self.family_modifier += 10
            elif self.average_ewg_score >= 6:
                self.family_modifier -= 15

        # Gentle modifier: penalize allergy concerns
        if self.allergy_concern_count > 0:
            self.gentle_modifier -= min(20, self.allergy_concern_count * 7)
        if self.average_ewg_score and self.average_ewg_score <= 2:
            self.gentle_modifier += 10

        # Skeptic modifier: reward CIR safe, penalize insufficient data
        if self.cir_safe_count > 5:
            self.skeptic_modifier += 15
        if self.cir_unsafe_count > 0:
            self.skeptic_modifier -= 20
        if self.unmatched_ingredients > self.matched_ingredients:
            self.skeptic_modifier -= 10  # Lots of unknowns

        # Clamp all modifiers to -30 to +30
        self.family_modifier = max(-30, min(30, self.family_modifier))
        self.gentle_modifier = max(-30, min(30, self.gentle_modifier))
        self.skeptic_modifier = max(-30, min(30, self.skeptic_modifier))

    def generate_summary(self):
        """Generate human-readable safety summary for Webflow."""
        parts = []

        # EWG summary
        if self.average_ewg_score:
            if self.average_ewg_score <= 2:
                parts.append(f"Low hazard (avg EWG: {self.average_ewg_score:.1f})")
            elif self.average_ewg_score <= 4:
                parts.append(f"Moderate hazard (avg EWG: {self.average_ewg_score:.1f})")
            else:
                parts.append(f"Higher hazard (avg EWG: {self.average_ewg_score:.1f})")

        # CIR summary
        if self.cir_safe_count > 0:
            parts.append(f"{self.cir_safe_count} CIR-safe ingredients")

        # Concerns
        if self.cancer_concern_count > 0:
            parts.append(f"{self.cancer_concern_count} cancer concern(s)")
        if self.allergy_concern_count > 0:
            parts.append(f"{self.allergy_concern_count} allergy concern(s)")

        # Coverage
        match_pct = (self.matched_ingredients / self.total_ingredients * 100) if self.total_ingredients > 0 else 0
        parts.append(f"{match_pct:.0f}% ingredients verified")

        self.safety_summary = " | ".join(parts)

        # Detailed list for safety-details field
        details = []
        if self.concerning_ingredients:
            details.append(f"Concerns: {', '.join(self.concerning_ingredients[:5])}")
        if self.controversial_ingredients:
            details.append(f"Controversial: {', '.join(self.controversial_ingredients[:3])}")
        if self.unknown_ingredients and len(self.unknown_ingredients) <= 5:
            details.append(f"Unknown: {', '.join(self.unknown_ingredients)}")

        self.safety_details = " | ".join(details)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON storage."""
        return {
            'product_slug': self.product_slug,
            'product_name': self.product_name,
            'total_ingredients': self.total_ingredients,
            'matched_ingredients': self.matched_ingredients,
            'unmatched_ingredients': self.unmatched_ingredients,
            'average_ewg_score': self.average_ewg_score,
            'max_ewg_score': self.max_ewg_score,
            'min_ewg_score': self.min_ewg_score,
            'cancer_concern_count': self.cancer_concern_count,
            'allergy_concern_count': self.allergy_concern_count,
            'developmental_concern_count': self.developmental_concern_count,
            'cir_safe_count': self.cir_safe_count,
            'cir_qualified_count': self.cir_qualified_count,
            'cir_unsafe_count': self.cir_unsafe_count,
            'clean_ingredients': self.clean_ingredients,
            'concerning_ingredients': self.concerning_ingredients,
            'unknown_ingredients': self.unknown_ingredients,
            'controversial_ingredients': self.controversial_ingredients,
            'family_modifier': self.family_modifier,
            'gentle_modifier': self.gentle_modifier,
            'skeptic_modifier': self.skeptic_modifier,
            'safety_summary': self.safety_summary,
            'safety_details': self.safety_details,
        }
