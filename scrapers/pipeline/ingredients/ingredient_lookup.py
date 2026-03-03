"""
Ingredient Lookup System

Looks up ingredients from product pages in the database and generates safety reports.
"""

from typing import List, Optional, Dict
from datetime import datetime

from .models import IngredientData, ProductSafetyReport
from .database import IngredientDatabase
from .ingredient_parser import IngredientParser


class IngredientLookup:
    """
    Looks up ingredients in the database and generates safety reports.
    Integrates with EWG and CIR scrapers when ingredients aren't in cache.
    """

    def __init__(self, db: IngredientDatabase = None, scrape_missing: bool = False):
        """
        Initialize the lookup system.

        Args:
            db: Database instance (creates default if None)
            scrape_missing: If True, scrape EWG/CIR for missing ingredients
        """
        self.db = db or IngredientDatabase()
        self.parser = IngredientParser()
        self.scrape_missing = scrape_missing

        # Lazy-load scrapers only if needed
        self._ewg_scraper = None
        self._cir_scraper = None

    @property
    def ewg_scraper(self):
        """Lazy-load EWG scraper."""
        if self._ewg_scraper is None and self.scrape_missing:
            from .ewg_scraper import EWGScraper
            self._ewg_scraper = EWGScraper(self.db)
        return self._ewg_scraper

    @property
    def cir_scraper(self):
        """Lazy-load CIR scraper."""
        if self._cir_scraper is None and self.scrape_missing:
            from .cir_scraper import CIRScraper
            self._cir_scraper = CIRScraper(self.db)
        return self._cir_scraper

    def lookup_ingredient(self, name: str) -> Optional[IngredientData]:
        """
        Look up a single ingredient by name.

        Args:
            name: Ingredient name (INCI or common name)

        Returns:
            IngredientData or None if not found
        """
        # Check database
        result = self.db.lookup(name)
        if result:
            return result

        # Optionally scrape missing ingredient
        if self.scrape_missing:
            # Try EWG first
            if self.ewg_scraper:
                result = self.ewg_scraper.scrape_and_save(name)
                if result:
                    return result

            # Try CIR
            if self.cir_scraper:
                result = self.cir_scraper.lookup_ingredient(name)
                if result:
                    return result

        return None

    def lookup_many(self, names: List[str]) -> Dict[str, Optional[IngredientData]]:
        """
        Look up multiple ingredients.

        Args:
            names: List of ingredient names

        Returns:
            Dict mapping names to IngredientData (or None if not found)
        """
        results = {}
        for name in names:
            results[name] = self.lookup_ingredient(name)
        return results

    def analyze_product(
        self,
        ingredient_text: str = None,
        ingredient_list: List[str] = None,
        product_slug: str = '',
        product_name: str = ''
    ) -> ProductSafetyReport:
        """
        Analyze a product's ingredients and generate a safety report.

        Args:
            ingredient_text: Raw ingredient list text (will be parsed)
            ingredient_list: Pre-parsed list of ingredients
            product_slug: Product identifier for the report
            product_name: Product name for display

        Returns:
            ProductSafetyReport with safety analysis
        """
        # Parse ingredients if text provided
        if ingredient_text and not ingredient_list:
            ingredient_list = self.parser.parse(ingredient_text)

        if not ingredient_list:
            return ProductSafetyReport(
                product_slug=product_slug,
                product_name=product_name,
                total_ingredients=0
            )

        # Create report
        report = ProductSafetyReport(
            product_slug=product_slug,
            product_name=product_name,
            total_ingredients=len(ingredient_list)
        )

        # Look up each ingredient
        ewg_scores = []

        for name in ingredient_list:
            ingredient = self.lookup_ingredient(name)

            if ingredient:
                report.matched_ingredients += 1
                report.ingredient_details.append(ingredient)

                # Track EWG score
                if ingredient.ewg_score:
                    ewg_scores.append(ingredient.ewg_score)

                # Categorize by safety
                if ingredient.is_clean:
                    report.clean_ingredients.append(name)
                elif ingredient.ewg_score and ingredient.ewg_score >= 7:
                    report.concerning_ingredients.append(name)
                elif ingredient.is_controversial:
                    report.controversial_ingredients.append(name)

                # Count concerns
                if ingredient.cancer_concern in ('Moderate', 'High'):
                    report.cancer_concern_count += 1
                    if name not in report.concerning_ingredients:
                        report.concerning_ingredients.append(name)

                if ingredient.allergy_concern in ('Moderate', 'High'):
                    report.allergy_concern_count += 1

                if ingredient.developmental_concern in ('Moderate', 'High'):
                    report.developmental_concern_count += 1
                    if name not in report.concerning_ingredients:
                        report.concerning_ingredients.append(name)

                # Count CIR determinations
                if ingredient.cir_safety:
                    if ingredient.cir_safety == 'Safe as used':
                        report.cir_safe_count += 1
                    elif ingredient.cir_safety == 'Safe with qualifications':
                        report.cir_qualified_count += 1
                    elif ingredient.cir_safety == 'Unsafe':
                        report.cir_unsafe_count += 1
                        report.concerning_ingredients.append(name)
                    elif ingredient.cir_safety == 'Insufficient data':
                        report.cir_insufficient_count += 1

            else:
                report.unmatched_ingredients += 1
                report.unknown_ingredients.append(name)

        # Calculate aggregate scores
        if ewg_scores:
            report.average_ewg_score = round(sum(ewg_scores) / len(ewg_scores), 2)
            report.max_ewg_score = max(ewg_scores)
            report.min_ewg_score = min(ewg_scores)

        # Calculate persona modifiers
        report.calculate_modifiers()

        # Generate summary text
        report.generate_summary()

        return report

    def analyze_url(self, url: str) -> ProductSafetyReport:
        """
        Fetch a product URL and analyze its ingredients.

        Args:
            url: Product page URL

        Returns:
            ProductSafetyReport with safety analysis
        """
        import requests
        from urllib.parse import urlparse

        # Extract slug from URL
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        slug = path_parts[-1] if path_parts else ''

        # Fetch page
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return ProductSafetyReport(product_slug=slug)

        # Extract ingredients
        ingredients, raw_text = self.parser.extract_from_html(resp.text)

        if not ingredients:
            print("Could not find ingredient list on page")
            return ProductSafetyReport(product_slug=slug)

        return self.analyze_product(
            ingredient_list=ingredients,
            product_slug=slug
        )


def analyze_ingredients(
    ingredient_text: str = None,
    ingredient_list: List[str] = None,
    product_slug: str = '',
    scrape_missing: bool = False
) -> ProductSafetyReport:
    """
    Convenience function to analyze ingredients.

    Args:
        ingredient_text: Raw ingredient list text
        ingredient_list: Pre-parsed ingredients
        product_slug: Product identifier
        scrape_missing: If True, scrape missing ingredients

    Returns:
        ProductSafetyReport
    """
    lookup = IngredientLookup(scrape_missing=scrape_missing)
    return lookup.analyze_product(
        ingredient_text=ingredient_text,
        ingredient_list=ingredient_list,
        product_slug=product_slug
    )


def print_safety_report(report: ProductSafetyReport):
    """Pretty-print a safety report."""
    print("=" * 60)
    print(f"INGREDIENT SAFETY REPORT: {report.product_name or report.product_slug}")
    print("=" * 60)

    print(f"\nIngredients: {report.total_ingredients} total")
    print(f"  Matched: {report.matched_ingredients}")
    print(f"  Unknown: {report.unmatched_ingredients}")

    if report.average_ewg_score:
        print(f"\nEWG Scores:")
        print(f"  Average: {report.average_ewg_score}")
        print(f"  Range: {report.min_ewg_score} - {report.max_ewg_score}")

    print(f"\nConcerns:")
    print(f"  Cancer: {report.cancer_concern_count}")
    print(f"  Allergy: {report.allergy_concern_count}")
    print(f"  Developmental: {report.developmental_concern_count}")

    if report.cir_safe_count or report.cir_qualified_count:
        print(f"\nCIR Status:")
        print(f"  Safe as used: {report.cir_safe_count}")
        print(f"  Safe with qualifications: {report.cir_qualified_count}")
        if report.cir_unsafe_count:
            print(f"  UNSAFE: {report.cir_unsafe_count}")

    if report.concerning_ingredients:
        print(f"\nConcerning ingredients:")
        for ing in report.concerning_ingredients[:10]:
            print(f"  - {ing}")

    if report.clean_ingredients:
        print(f"\nClean ingredients: {len(report.clean_ingredients)}")

    print(f"\nPersona Score Modifiers:")
    print(f"  Family: {report.family_modifier:+d}")
    print(f"  Gentle: {report.gentle_modifier:+d}")
    print(f"  Skeptic: {report.skeptic_modifier:+d}")

    if report.safety_summary:
        print(f"\nSummary: {report.safety_summary}")

    print("=" * 60)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python ingredient_lookup.py 'Water, Glycerin, Retinol'")
        print("  python ingredient_lookup.py --url https://brand.com/product")
        print("  python ingredient_lookup.py --ingredient 'Glycerin'")
        sys.exit(1)

    lookup = IngredientLookup(scrape_missing=True)

    if sys.argv[1] == '--url':
        # Analyze URL
        url = sys.argv[2]
        print(f"Analyzing: {url}\n")
        report = lookup.analyze_url(url)
        print_safety_report(report)

    elif sys.argv[1] == '--ingredient':
        # Look up single ingredient
        name = ' '.join(sys.argv[2:])
        print(f"Looking up: {name}\n")
        ingredient = lookup.lookup_ingredient(name)
        if ingredient:
            print(f"Name: {ingredient.inci_name}")
            print(f"EWG Score: {ingredient.ewg_score}")
            print(f"EWG Level: {ingredient.ewg_concern_level}")
            print(f"CIR Safety: {ingredient.cir_safety}")
            print(f"Cancer Concern: {ingredient.cancer_concern}")
            print(f"Allergy Concern: {ingredient.allergy_concern}")
            print(f"Is Clean: {ingredient.is_clean}")
        else:
            print("Not found")

    else:
        # Analyze ingredient list
        text = ' '.join(sys.argv[1:])
        print(f"Analyzing ingredients:\n{text}\n")
        report = lookup.analyze_product(ingredient_text=text, product_slug='test')
        print_safety_report(report)
