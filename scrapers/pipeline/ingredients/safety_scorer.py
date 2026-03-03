"""
Safety Scorer - Calculates ingredient-based safety metrics for products.

Integrates with the existing pipeline to add safety analysis to classified products.
"""

from typing import Dict, Optional, List

from .models import ProductSafetyReport
from .database import IngredientDatabase
from .ingredient_lookup import IngredientLookup
from .ingredient_parser import IngredientParser


class SafetyScorer:
    """
    Calculates ingredient-based safety metrics for products.
    Designed to integrate with the existing iHeartClean pipeline.
    """

    def __init__(self, db: IngredientDatabase = None, scrape_missing: bool = False):
        """
        Initialize the safety scorer.

        Args:
            db: Ingredient database (creates default if None)
            scrape_missing: If True, scrape EWG/CIR for unknown ingredients
        """
        self.db = db or IngredientDatabase()
        self.lookup = IngredientLookup(db=self.db, scrape_missing=scrape_missing)
        self.parser = IngredientParser()

    def analyze_product(
        self,
        product: Dict,
        ingredient_text: str = None
    ) -> ProductSafetyReport:
        """
        Analyze a classified product and generate a safety report.

        Args:
            product: Classified product dict from pipeline
            ingredient_text: Raw ingredient list (uses product['ingredients'] if not provided)

        Returns:
            ProductSafetyReport with safety analysis
        """
        # Get ingredients from product if not provided
        if not ingredient_text:
            ingredient_text = product.get('ingredients', '')

        # Parse ingredients
        ingredients = self.parser.parse(ingredient_text) if ingredient_text else []

        # Generate report
        report = self.lookup.analyze_product(
            ingredient_list=ingredients,
            product_slug=product.get('slug', ''),
            product_name=product.get('name', '')
        )

        return report

    def enrich_product(self, product: Dict, ingredient_text: str = None) -> Dict:
        """
        Add ingredient safety data to a classified product.
        Modifies the product dict in-place and returns it.

        Args:
            product: Classified product dict from pipeline
            ingredient_text: Raw ingredient list (optional)

        Returns:
            Enriched product dict with safety data
        """
        report = self.analyze_product(product, ingredient_text)

        # Add safety report to product
        product['safety_report'] = report.to_dict()

        # Add key metrics directly
        product['average_ewg_score'] = report.average_ewg_score
        product['max_ewg_score'] = report.max_ewg_score
        product['ingredient_match_count'] = report.matched_ingredients
        product['ingredient_total_count'] = report.total_ingredients

        # Add concern counts
        product['cancer_concern_ingredients'] = report.cancer_concern_count
        product['allergy_concern_ingredients'] = report.allergy_concern_count

        # Add lists for UI
        product['concerning_ingredients'] = report.concerning_ingredients[:5]
        product['clean_ingredient_count'] = len(report.clean_ingredients)

        # Add safety summaries for Webflow
        product['safety_summary'] = report.safety_summary
        product['ingredient_safety_details'] = report.safety_details

        # Apply persona score modifiers
        self._apply_persona_modifiers(product, report)

        return product

    def _apply_persona_modifiers(self, product: Dict, report: ProductSafetyReport):
        """
        Apply ingredient-based persona score modifiers.
        Modifies product dict in-place.
        """
        persona = product.get('persona_relevance', {})

        # Family score: Penalize cancer/developmental concerns
        family_key = self._find_persona_key(persona, 'family')
        if family_key:
            current = persona.get(family_key, 50)
            persona[family_key] = max(0, min(100, current + report.family_modifier))

        # Gentle score: Penalize allergy concerns
        gentle_key = self._find_persona_key(persona, 'gentle')
        if gentle_key:
            current = persona.get(gentle_key, 50)
            persona[gentle_key] = max(0, min(100, current + report.gentle_modifier))

        # Skeptic score: Reward CIR safe, penalize unknowns
        skeptic_key = self._find_persona_key(persona, 'skeptic')
        if skeptic_key:
            current = persona.get(skeptic_key, 50)
            persona[skeptic_key] = max(0, min(100, current + report.skeptic_modifier))

        product['persona_relevance'] = persona

    def _find_persona_key(self, persona: Dict, name: str) -> Optional[str]:
        """Find the persona key that matches a name."""
        name_lower = name.lower()
        for key in persona.keys():
            if name_lower in key.lower():
                return key
        return None

    def generate_safety_details_text(self, report: ProductSafetyReport) -> str:
        """
        Generate safety details text for Webflow safety-details field.
        Format: icon-key: Detail1; Detail2 | icon-key2: Detail1

        Args:
            report: ProductSafetyReport

        Returns:
            Formatted safety details string
        """
        parts = []

        # EWG rating
        if report.average_ewg_score:
            if report.average_ewg_score <= 2:
                parts.append("safety-certifications: EWG Low Hazard")
            elif report.average_ewg_score <= 4:
                parts.append("safety-certifications: EWG Moderate")
            else:
                parts.append("safety-alert: EWG Higher Concern")

        # CIR status
        if report.cir_safe_count > 3:
            parts.append(f"safety-tested: {report.cir_safe_count} CIR Verified Safe")

        # Concerns
        if report.cancer_concern_count > 0:
            parts.append(f"safety-alert: {report.cancer_concern_count} Cancer Concern(s)")

        if report.allergy_concern_count > 0:
            parts.append(f"safety-alert: {report.allergy_concern_count} Allergy Concern(s)")

        # Coverage
        if report.total_ingredients > 0:
            pct = (report.matched_ingredients / report.total_ingredients) * 100
            if pct >= 80:
                parts.append(f"safety-check: {pct:.0f}% Ingredients Verified")
            elif pct >= 50:
                parts.append(f"safety-check: {pct:.0f}% Ingredients Known")

        return " | ".join(parts)


def enrich_product_with_safety(product: Dict, scrape_missing: bool = False) -> Dict:
    """
    Convenience function to add safety data to a classified product.

    Args:
        product: Classified product dict from pipeline
        scrape_missing: If True, scrape EWG/CIR for unknown ingredients

    Returns:
        Enriched product dict
    """
    scorer = SafetyScorer(scrape_missing=scrape_missing)
    return scorer.enrich_product(product)


def get_product_safety_summary(product: Dict) -> str:
    """
    Get a one-line safety summary for a product.

    Args:
        product: Classified product dict (with or without safety data)

    Returns:
        Safety summary string
    """
    # Check if already analyzed
    if 'safety_summary' in product:
        return product['safety_summary']

    # Quick analysis
    scorer = SafetyScorer()
    report = scorer.analyze_product(product)
    return report.safety_summary


if __name__ == '__main__':
    # Test with sample product
    sample_product = {
        'name': 'Hydrating Face Cream',
        'slug': 'test-cream',
        'brand': 'Test Brand',
        'ingredients': 'Water, Glycerin, Butylene Glycol, Dimethicone, Niacinamide, '
                       'Tocopherol, Phenoxyethanol, Hyaluronic Acid, Retinol',
        'persona_relevance': {
            'family_mom': 60,
            'gentle_sensitive': 55,
            'skeptic_professional': 50,
        }
    }

    print("Testing SafetyScorer...")
    scorer = SafetyScorer()

    # Analyze product
    report = scorer.analyze_product(sample_product)
    print(f"\nSafety Report:")
    print(f"  Ingredients: {report.total_ingredients}")
    print(f"  Matched: {report.matched_ingredients}")
    print(f"  Avg EWG: {report.average_ewg_score}")
    print(f"  Summary: {report.safety_summary}")

    # Enrich product
    enriched = scorer.enrich_product(sample_product)
    print(f"\nEnriched Product:")
    print(f"  average_ewg_score: {enriched.get('average_ewg_score')}")
    print(f"  safety_summary: {enriched.get('safety_summary')}")
    print(f"  Persona (after modifiers):")
    for k, v in enriched.get('persona_relevance', {}).items():
        print(f"    {k}: {v}")
