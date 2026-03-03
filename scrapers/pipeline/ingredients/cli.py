#!/usr/bin/env python3
"""
Ingredient Database CLI

Command-line interface for managing the cosmetic ingredient database.

Usage:
    python -m ingredients.cli scrape-ewg --limit 100
    python -m ingredients.cli scrape-cir --full
    python -m ingredients.cli lookup "Glycerin"
    python -m ingredients.cli analyze "Water, Glycerin, Retinol"
    python -m ingredients.cli sync --push
    python -m ingredients.cli stats
"""

import os
import sys
import argparse
from typing import List
from pathlib import Path

# Load .env file from pipeline directory
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from .database import IngredientDatabase, seed_common_aliases
from .ewg_scraper import EWGScraper, scrape_common_ingredients
from .cir_scraper import CIRScraper, scrape_cir_database
from .cosing_scraper import CosIngScraper, scrape_cosing_batch
from .pubchem_scraper import PubChemScraper, enrich_ingredients_from_pubchem
from .ingredient_lookup import IngredientLookup, print_safety_report
from .ingredient_parser import IngredientParser
from .webflow_sync import WebflowIngredientSync, sync_to_webflow


def cmd_scrape_ewg(args):
    """Scrape EWG Skin Deep database."""
    db = IngredientDatabase()
    scraper = EWGScraper(db)

    if args.ingredient:
        # Scrape single ingredient
        print(f"Scraping: {args.ingredient}")
        ingredient = scraper.scrape_and_save(args.ingredient)
        if ingredient:
            print(f"  Name: {ingredient.inci_name}")
            print(f"  EWG Score: {ingredient.ewg_score}")
            print(f"  Concern Level: {ingredient.ewg_concern_level}")
            print(f"  Cancer: {ingredient.cancer_concern}")
            print(f"  Allergy: {ingredient.allergy_concern}")
            print(f"  Is Clean: {ingredient.is_clean}")
        else:
            print("  Not found")
    else:
        # Batch scrape common ingredients
        print(f"Scraping common cosmetic ingredients...")
        count = scrape_common_ingredients(db)
        print(f"\nScraped {count} ingredients")

    print(f"\nDatabase stats: {db.get_stats()}")


def cmd_scrape_cir(args):
    """Scrape CIR database."""
    db = IngredientDatabase()

    if args.full:
        print("Scraping full CIR database (this may take a while)...")
        stats = scrape_cir_database(db)
        print(f"\nScraped {stats['ingredients_found']} ingredients")
    elif args.letters:
        print(f"Scraping CIR letters: {args.letters.upper()}")
        stats = scrape_cir_database(db, letters=args.letters)
        print(f"\nScraped {stats['ingredients_found']} ingredients")
    elif args.ingredient:
        scraper = CIRScraper(db)
        print(f"Looking up: {args.ingredient}")
        ingredient = scraper.lookup_ingredient(args.ingredient)
        if ingredient:
            print(f"  Name: {ingredient.inci_name}")
            print(f"  CIR Safety: {ingredient.cir_safety}")
            print(f"  Conditions: {ingredient.cir_conditions}")
        else:
            print("  Not found in CIR")
    else:
        print("Specify --full, --letters ABC, or --ingredient 'Name'")

    print(f"\nDatabase stats: {db.get_stats()}")


def cmd_lookup(args):
    """Look up an ingredient."""
    db = IngredientDatabase()
    lookup = IngredientLookup(db, scrape_missing=args.scrape)

    name = ' '.join(args.name) if isinstance(args.name, list) else args.name
    print(f"Looking up: {name}\n")

    ingredient = lookup.lookup_ingredient(name)

    if ingredient:
        print(f"Name: {ingredient.inci_name}")
        print(f"Slug: {ingredient.slug}")

        if ingredient.common_names:
            print(f"Also known as: {', '.join(ingredient.common_names)}")

        print(f"\nEWG Data:")
        print(f"  Score: {ingredient.ewg_score or 'N/A'}")
        print(f"  Concern Level: {ingredient.ewg_concern_level or 'N/A'}")
        print(f"  Cancer Concern: {ingredient.cancer_concern or 'N/A'}")
        print(f"  Allergy Concern: {ingredient.allergy_concern or 'N/A'}")
        print(f"  Developmental: {ingredient.developmental_concern or 'N/A'}")

        print(f"\nCIR Data:")
        print(f"  Safety: {ingredient.cir_safety or 'N/A'}")
        print(f"  Conditions: {ingredient.cir_conditions or 'N/A'}")

        print(f"\nStatus:")
        print(f"  Is Clean: {ingredient.is_clean}")
        print(f"  Is Controversial: {ingredient.is_controversial}")
        print(f"  Function: {ingredient.function or 'N/A'}")

        if ingredient.ewg_url:
            print(f"\nEWG URL: {ingredient.ewg_url}")
    else:
        print("Not found in database")
        if not args.scrape:
            print("Try --scrape to search EWG/CIR")


def cmd_analyze(args):
    """Analyze a product's ingredients."""
    db = IngredientDatabase()
    lookup = IngredientLookup(db, scrape_missing=args.scrape)

    if args.url:
        print(f"Fetching: {args.url}\n")
        report = lookup.analyze_url(args.url)
    else:
        text = ' '.join(args.ingredients)
        print(f"Analyzing: {text[:100]}...\n")
        report = lookup.analyze_product(ingredient_text=text, product_slug='cli-analysis')

    print_safety_report(report)


def cmd_sync(args):
    """Sync ingredients to Webflow."""
    if args.info:
        sync = WebflowIngredientSync()
        print("\nWebflow Collections:")
        for col in sync.list_collections():
            print(f"  - {col.get('displayName')}: {col.get('id')}")

        if sync.collection_id:
            print(f"\nIngredients collection ({sync.collection_id}):")
            info = sync.get_collection_info()
            if info:
                for field in info.get('fields', []):
                    print(f"  - {field.get('slug')}: {field.get('type')}")
    else:
        print(f"Syncing ingredients to Webflow (limit: {args.limit})...\n")
        stats = sync_to_webflow(limit=args.limit, unsynced_only=not args.all)
        print(f"\nSync complete:")
        print(f"  Total: {stats['total']}")
        print(f"  Success: {stats['success']}")
        print(f"  Failed: {stats['failed']}")


def cmd_stats(args):
    """Show database statistics."""
    db = IngredientDatabase()
    stats = db.get_stats()

    print("\nIngredient Database Statistics")
    print("=" * 40)
    print(f"Total ingredients: {stats['total']}")
    print(f"With EWG data: {stats['with_ewg']}")
    print(f"With CIR data: {stats['with_cir']}")
    print(f"Clean ingredients: {stats['clean']}")
    print(f"High concern (EWG 7+): {stats['high_concern']}")
    print(f"Synced to Webflow: {stats['synced_to_webflow']}")
    if stats['average_ewg_score']:
        print(f"Average EWG score: {stats['average_ewg_score']}")


def cmd_seed(args):
    """Seed database with common aliases."""
    db = IngredientDatabase()
    print("Seeding common ingredient aliases...")
    seed_common_aliases(db)
    print("Done!")


def cmd_search(args):
    """Search for ingredients."""
    db = IngredientDatabase()
    query = ' '.join(args.query)
    print(f"Searching for: {query}\n")

    results = db.search(query, limit=args.limit)

    if results:
        for i, ing in enumerate(results, 1):
            ewg = f"EWG {ing.ewg_score}" if ing.ewg_score else "No EWG"
            cir = ing.cir_safety or "No CIR"
            print(f"{i}. {ing.inci_name} ({ewg}, {cir})")
    else:
        print("No results found")


def cmd_scrape_cosing(args):
    """Scrape CosIng (EU) database for CAS#, EC#, and functions."""
    db = IngredientDatabase()
    scraper = CosIngScraper(db)

    if args.ingredient:
        # Lookup single ingredient
        name = ' '.join(args.ingredient) if isinstance(args.ingredient, list) else args.ingredient
        print(f"Looking up in CosIng: {name}\n")
        result = scraper.lookup_and_update(name)
        if result:
            print(f"  INCI: {result.get('inci_name')}")
            print(f"  CAS#: {result.get('cas_number', 'N/A')}")
            print(f"  EC#: {result.get('ec_number', 'N/A')}")
            if result.get('functions'):
                print(f"  Functions: {', '.join(result['functions'])}")
        else:
            print("  Not found in CosIng")
    else:
        # Batch enrich existing ingredients
        print("Enriching existing ingredients with CosIng data...")
        ingredients = db.get_all(limit=args.limit)
        names = [ing.inci_name for ing in ingredients if not ing.cas_number]
        if names:
            stats = scrape_cosing_batch(db, names[:args.limit])
            print(f"\nCosIng enrichment: {stats['found']} found, {stats['not_found']} not found")
        else:
            print("No ingredients need CosIng data")

    print(f"\nDatabase stats: {db.get_stats()}")


def cmd_scrape_pubchem(args):
    """Scrape PubChem for chemistry/molecular data."""
    db = IngredientDatabase()
    scraper = PubChemScraper(db)

    if args.ingredient:
        # Lookup single ingredient
        name = ' '.join(args.ingredient) if isinstance(args.ingredient, list) else args.ingredient
        print(f"Looking up in PubChem: {name}\n")
        result = scraper.get_full_compound_data(name)
        if result:
            print(f"  PubChem CID: {result.get('pubchem_cid')}")
            print(f"  Formula: {result.get('molecular_formula', 'N/A')}")
            print(f"  MW: {result.get('molecular_weight', 'N/A')}")
            if result.get('synonyms'):
                print(f"  Synonyms: {', '.join(result['synonyms'][:5])}")
            if result.get('description'):
                print(f"  Description: {result['description'][:200]}...")
            if result.get('physical_properties'):
                props = result['physical_properties']
                if props.get('form'):
                    print(f"  Form: {props['form']}")
                if props.get('odor'):
                    print(f"  Scent: {props['odor']}")
            if result.get('medicinal_uses'):
                print(f"  Medicinal: {result['medicinal_uses'][:150]}...")
        else:
            print("  Not found in PubChem")
    else:
        # Batch enrich existing ingredients
        print(f"Enriching up to {args.limit} ingredients with PubChem data...")
        stats = enrich_ingredients_from_pubchem(db, limit=args.limit)
        print(f"\nPubChem enrichment: {stats['enriched']} enriched, {stats['not_found']} not found")

    print(f"\nDatabase stats: {db.get_stats()}")


def cmd_enrich(args):
    """Enrich ingredients from all data sources."""
    db = IngredientDatabase()
    ingredients = db.get_all(limit=args.limit)

    print(f"Enriching {len(ingredients)} ingredients from all sources...\n")

    # EWG
    if not args.skip_ewg:
        print("1. Scraping EWG data...")
        ewg_scraper = EWGScraper(db)
        ewg_count = 0
        for ing in ingredients:
            if not ing.ewg_score:
                result = ewg_scraper.scrape_and_save(ing.inci_name)
                if result:
                    ewg_count += 1
        print(f"   Added EWG data to {ewg_count} ingredients")

    # CosIng
    if not args.skip_cosing:
        print("2. Scraping CosIng data...")
        cosing_scraper = CosIngScraper(db)
        cosing_count = 0
        for ing in ingredients:
            if not ing.cas_number:
                result = cosing_scraper.lookup_and_update(ing.inci_name)
                if result:
                    cosing_count += 1
        print(f"   Added CosIng data to {cosing_count} ingredients")

    # PubChem
    if not args.skip_pubchem:
        print("3. Scraping PubChem data...")
        stats = enrich_ingredients_from_pubchem(db, limit=args.limit)
        print(f"   Added PubChem data to {stats['enriched']} ingredients")

    # Compute persona scores and safety text
    print("4. Computing persona scores and safety summaries...")
    for ing in db.get_all(limit=args.limit):
        ing.compute_persona_scores()
        ing.generate_safety_concerns_text()
        ing.infer_kind()
        db.upsert(ing)

    print(f"\nEnrichment complete!")
    print(f"Database stats: {db.get_stats()}")


def main():
    parser = argparse.ArgumentParser(
        description='Ingredient Database CLI for iHeartClean.beauty',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m ingredients.cli scrape-ewg                     # Scrape common EWG ingredients
  python -m ingredients.cli scrape-ewg --ingredient Water  # Scrape specific ingredient
  python -m ingredients.cli scrape-cir --letters AB        # Scrape CIR A-B
  python -m ingredients.cli scrape-cir --full              # Scrape full CIR database
  python -m ingredients.cli lookup Glycerin                # Look up ingredient
  python -m ingredients.cli lookup Retinol --scrape        # Look up + scrape if missing
  python -m ingredients.cli analyze "Water, Glycerin, Retinol"  # Analyze ingredient list
  python -m ingredients.cli sync --push --limit 50         # Sync 50 to Webflow
  python -m ingredients.cli stats                          # Show database stats
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # scrape-ewg
    ewg_parser = subparsers.add_parser('scrape-ewg', help='Scrape EWG Skin Deep')
    ewg_parser.add_argument('--ingredient', '-i', help='Specific ingredient to scrape')
    ewg_parser.add_argument('--limit', '-l', type=int, default=100, help='Max ingredients')
    ewg_parser.set_defaults(func=cmd_scrape_ewg)

    # scrape-cir
    cir_parser = subparsers.add_parser('scrape-cir', help='Scrape CIR database')
    cir_parser.add_argument('--full', action='store_true', help='Scrape full database')
    cir_parser.add_argument('--letters', '-l', help='Specific letters (e.g., ABC)')
    cir_parser.add_argument('--ingredient', '-i', help='Look up specific ingredient')
    cir_parser.set_defaults(func=cmd_scrape_cir)

    # lookup
    lookup_parser = subparsers.add_parser('lookup', help='Look up an ingredient')
    lookup_parser.add_argument('name', nargs='+', help='Ingredient name')
    lookup_parser.add_argument('--scrape', '-s', action='store_true', help='Scrape if not found')
    lookup_parser.set_defaults(func=cmd_lookup)

    # analyze
    analyze_parser = subparsers.add_parser('analyze', help='Analyze product ingredients')
    analyze_parser.add_argument('ingredients', nargs='*', help='Ingredient list text')
    analyze_parser.add_argument('--url', '-u', help='Product URL to analyze')
    analyze_parser.add_argument('--scrape', '-s', action='store_true', help='Scrape missing')
    analyze_parser.set_defaults(func=cmd_analyze)

    # sync
    sync_parser = subparsers.add_parser('sync', help='Sync to Webflow')
    sync_parser.add_argument('--push', action='store_true', help='Actually push to Webflow')
    sync_parser.add_argument('--limit', '-l', type=int, default=100, help='Max to sync')
    sync_parser.add_argument('--all', '-a', action='store_true', help='Sync all (not just unsynced)')
    sync_parser.add_argument('--info', action='store_true', help='Show collection info')
    sync_parser.set_defaults(func=cmd_sync)

    # stats
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    stats_parser.set_defaults(func=cmd_stats)

    # seed
    seed_parser = subparsers.add_parser('seed', help='Seed common aliases')
    seed_parser.set_defaults(func=cmd_seed)

    # search
    search_parser = subparsers.add_parser('search', help='Search ingredients')
    search_parser.add_argument('query', nargs='+', help='Search query')
    search_parser.add_argument('--limit', '-l', type=int, default=10, help='Max results')
    search_parser.set_defaults(func=cmd_search)

    # scrape-cosing
    cosing_parser = subparsers.add_parser('scrape-cosing', help='Scrape CosIng (EU) for CAS#, EC#')
    cosing_parser.add_argument('--ingredient', '-i', nargs='+', help='Specific ingredient')
    cosing_parser.add_argument('--limit', '-l', type=int, default=100, help='Max to enrich')
    cosing_parser.set_defaults(func=cmd_scrape_cosing)

    # scrape-pubchem
    pubchem_parser = subparsers.add_parser('scrape-pubchem', help='Scrape PubChem for chemistry data')
    pubchem_parser.add_argument('--ingredient', '-i', nargs='+', help='Specific ingredient')
    pubchem_parser.add_argument('--limit', '-l', type=int, default=100, help='Max to enrich')
    pubchem_parser.set_defaults(func=cmd_scrape_pubchem)

    # enrich
    enrich_parser = subparsers.add_parser('enrich', help='Enrich ingredients from all sources')
    enrich_parser.add_argument('--limit', '-l', type=int, default=100, help='Max ingredients')
    enrich_parser.add_argument('--skip-ewg', action='store_true', help='Skip EWG scraping')
    enrich_parser.add_argument('--skip-cosing', action='store_true', help='Skip CosIng scraping')
    enrich_parser.add_argument('--skip-pubchem', action='store_true', help='Skip PubChem scraping')
    enrich_parser.set_defaults(func=cmd_enrich)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == '__main__':
    main()
