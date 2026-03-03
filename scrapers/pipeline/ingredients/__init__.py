"""
Ingredient Database Module for iHeartClean.beauty

Provides scrapers for EWG Skin Deep and CIR databases,
local SQLite caching, and Webflow CMS integration.

Usage:
    from ingredients import IngredientLookup, SafetyScorer

    # Look up a single ingredient
    lookup = IngredientLookup()
    ingredient = lookup.lookup_ingredient("Glycerin")

    # Analyze a product's ingredients
    report = lookup.analyze_product(ingredient_text="Water, Glycerin, Retinol")

    # Enrich a classified product with safety data
    from ingredients import enrich_product_with_safety
    enriched = enrich_product_with_safety(classified_product)

CLI:
    python -m ingredients.cli scrape-ewg       # Scrape EWG database
    python -m ingredients.cli scrape-cir       # Scrape CIR database
    python -m ingredients.cli lookup Glycerin  # Look up ingredient
    python -m ingredients.cli analyze "..."    # Analyze ingredient list
    python -m ingredients.cli sync --push      # Sync to Webflow
    python -m ingredients.cli stats            # Show database stats
"""

from .models import IngredientData, ProductSafetyReport
from .database import IngredientDatabase
from .ingredient_lookup import IngredientLookup, analyze_ingredients
from .ingredient_parser import IngredientParser, parse_ingredient_list
from .safety_scorer import SafetyScorer, enrich_product_with_safety
from .ewg_scraper import EWGScraper, scrape_common_ingredients
from .cir_scraper import CIRScraper, scrape_cir_database
from .cosing_scraper import CosIngScraper, scrape_cosing_batch
from .pubchem_scraper import PubChemScraper, enrich_ingredients_from_pubchem
from .webflow_sync import WebflowIngredientSync, sync_to_webflow

__all__ = [
    # Data models
    'IngredientData',
    'ProductSafetyReport',

    # Database
    'IngredientDatabase',

    # Lookup and analysis
    'IngredientLookup',
    'analyze_ingredients',

    # Parsing
    'IngredientParser',
    'parse_ingredient_list',

    # Safety scoring (pipeline integration)
    'SafetyScorer',
    'enrich_product_with_safety',

    # Scrapers
    'EWGScraper',
    'scrape_common_ingredients',
    'CIRScraper',
    'scrape_cir_database',
    'CosIngScraper',
    'scrape_cosing_batch',
    'PubChemScraper',
    'enrich_ingredients_from_pubchem',

    # Webflow sync
    'WebflowIngredientSync',
    'sync_to_webflow',
]
