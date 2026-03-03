#!/usr/bin/env python3
"""
Scrape PubMed for ingredient research data.

Uses NCBI E-utilities API (free, no key required for low volume).
Searches for cosmetic/skincare research on each ingredient.

Usage:
    python scrape_pubmed_ingredients.py --limit 100
    python scrape_pubmed_ingredients.py --all
"""

import os
import sys
import time
import csv
import re
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import xml.etree.ElementTree as ET

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

import requests
import functools
print = functools.partial(print, flush=True)

# PubMed E-utilities endpoints
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Webflow API
WEBFLOW_API_BASE = "https://api.webflow.com/v2"
INGREDIENTS_COLLECTION_ID = "67b25dbc040723aed519bf6f"

# Output file
OUTPUT_CSV = Path(__file__).parent / 'data' / 'pubmed_ingredient_research.csv'


def clean_ingredient_name(name: str) -> str:
    """Clean ingredient name for PubMed search."""
    # Remove parenthetical common names like "Zingiber Officinale (Ginger)"
    # Keep the scientific name for better PubMed results
    name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    # Remove extra whitespace
    name = ' '.join(name.split())
    return name.strip()


def extract_search_variants(name: str) -> List[str]:
    """
    Extract multiple search variants from an ingredient name.
    Returns list of terms to try, most specific first.
    """
    variants = []

    # Original name (cleaned)
    clean = clean_ingredient_name(name)
    variants.append(clean)

    # Extract common name from parentheses: "Zingiber Officinale (Ginger)" -> "Ginger"
    match = re.search(r'\(([^)]+)\)', name)
    if match:
        common_name = match.group(1).strip()
        if common_name and len(common_name) > 2:
            variants.append(common_name)

    # Extract genus (first word of scientific name): "Zingiber Officinale" -> "Zingiber"
    words = clean.split()
    if len(words) >= 2 and words[0][0].isupper():
        genus = words[0]
        if len(genus) > 3:
            variants.append(genus)

    # For compound names, try without qualifiers like "Root", "Leaf", "Extract", etc.
    qualifiers = ['root', 'leaf', 'seed', 'flower', 'bark', 'fruit', 'oil', 'extract',
                  'powder', 'juice', 'water', 'butter', 'wax', 'cell', 'culture']
    base_name = clean.lower()
    for q in qualifiers:
        base_name = re.sub(rf'\b{q}\b', '', base_name)
    base_name = ' '.join(base_name.split()).strip()
    if base_name and base_name != clean.lower() and len(base_name) > 3:
        variants.append(base_name.title())

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for v in variants:
        v_lower = v.lower()
        if v_lower not in seen and len(v) > 2:
            seen.add(v_lower)
            unique.append(v)

    return unique


def search_pubmed(ingredient_name: str, max_results: int = 20) -> Dict:
    """
    Search PubMed for an ingredient.
    Tries multiple search variants to find the best results.
    Prefers specific results (5-500 papers) over too broad (1000+) or too narrow (0).

    Returns dict with:
    - total_results: Total number of papers found
    - paper_ids: List of PubMed IDs
    - search_term: The actual search term used
    - variant_used: Which name variant found results
    """
    variants = extract_search_variants(ingredient_name)

    best_result = {
        'total_results': 0,
        'paper_ids': [],
        'search_term': '',
        'variant_used': '',
    }

    # Track all results to pick the best
    all_results = []

    for variant in variants:
        # Build search query - focus specifically on topical/cosmetic use
        query = f'"{variant}"[Title/Abstract] AND (cosmetic[Title/Abstract] OR skincare[Title/Abstract] OR "topical application"[Title/Abstract] OR "skin care"[Title/Abstract] OR dermatological[Title/Abstract])'

        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'retmode': 'json',
            'sort': 'relevance',
        }

        try:
            resp = requests.get(ESEARCH_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            result = data.get('esearchresult', {})
            total = int(result.get('count', 0))
            ids = result.get('idlist', [])

            all_results.append({
                'total_results': total,
                'paper_ids': ids,
                'search_term': query,
                'variant_used': variant,
            })

            # If we found a good specific result (5-500 papers), use it
            if 5 <= total <= 500:
                best_result = all_results[-1]
                break

            time.sleep(0.35)  # Rate limit between variant searches

        except Exception as e:
            continue

    # If we didn't find an ideal result, pick the best one
    if best_result['total_results'] == 0 and all_results:
        # Prefer results in the 1-1000 range, then anything > 0
        for r in all_results:
            if 1 <= r['total_results'] <= 1000:
                best_result = r
                break
        # If still nothing, take first non-zero result but cap at 1000
        if best_result['total_results'] == 0:
            for r in all_results:
                if r['total_results'] > 0:
                    best_result = r
                    # Mark as "broad" if too many results
                    if r['total_results'] > 1000:
                        best_result['too_broad'] = True
                    break

    if not best_result['search_term']:
        best_result['search_term'] = f'"{variants[0]}"[Title/Abstract]' if variants else ingredient_name

    return best_result


def get_paper_summaries(paper_ids: List[str]) -> List[Dict]:
    """Get summary info for a list of PubMed IDs."""
    if not paper_ids:
        return []

    params = {
        'db': 'pubmed',
        'id': ','.join(paper_ids[:10]),  # Limit to 10 papers
        'retmode': 'json',
    }

    try:
        resp = requests.get(ESUMMARY_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        summaries = []
        result = data.get('result', {})

        for pid in paper_ids[:10]:
            paper = result.get(pid, {})
            if paper:
                summaries.append({
                    'pmid': pid,
                    'title': paper.get('title', ''),
                    'source': paper.get('source', ''),  # Journal
                    'pubdate': paper.get('pubdate', ''),
                    'authors': ', '.join([a.get('name', '') for a in paper.get('authors', [])[:3]]),
                })

        return summaries
    except Exception as e:
        print(f"  Summary error: {e}")
        return []


def categorize_research(total_results: int, summaries: List[Dict]) -> Dict:
    """
    Categorize the research level for an ingredient.

    Returns:
    - research_level: 'extensive', 'moderate', 'limited', 'minimal'
    - evidence_quality: based on journal types and recency
    """
    if total_results >= 100:
        level = 'extensive'
    elif total_results >= 20:
        level = 'moderate'
    elif total_results >= 5:
        level = 'limited'
    else:
        level = 'minimal'

    # Check for recent research (2020+)
    recent_count = 0
    for s in summaries:
        pubdate = s.get('pubdate', '')
        if any(year in pubdate for year in ['2024', '2023', '2022', '2021', '2020']):
            recent_count += 1

    return {
        'research_level': level,
        'recent_papers': recent_count,
        'has_recent_research': recent_count > 0,
    }


def get_webflow_ingredients(limit: Optional[int] = None) -> List[Dict]:
    """Fetch ingredients from Webflow."""
    api_token = os.environ.get('WEBFLOW_API_TOKEN', '')
    if not api_token:
        raise ValueError("WEBFLOW_API_TOKEN not set")

    session = requests.Session()
    session.headers.update({
        'Authorization': f'Bearer {api_token}',
        'Accept': 'application/json',
    })

    print("Loading ingredients from Webflow...")
    items = []
    offset = 0

    while True:
        resp = session.get(
            f'{WEBFLOW_API_BASE}/collections/{INGREDIENTS_COLLECTION_ID}/items?limit=100&offset={offset}'
        )
        if not resp.ok:
            print(f"API error: {resp.status_code}")
            break

        data = resp.json()
        batch = data.get('items', [])
        if not batch:
            break

        items.extend(batch)
        print(f"  Loaded {len(items)}...", end='\r')

        if len(batch) < 100:
            break
        offset += 100

        if limit and len(items) >= limit:
            items = items[:limit]
            break

        time.sleep(0.5)  # Rate limiting

    print(f"  Loaded {len(items)} ingredients total")
    return items


def main():
    print("=" * 70)
    print("PUBMED INGREDIENT RESEARCH SCRAPER")
    print("=" * 70)
    print()

    args = sys.argv[1:]
    limit = None

    for i, arg in enumerate(args):
        if arg == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1])

    if '--all' not in args and limit is None:
        print(__doc__)
        print("\nUsage:")
        print("  python scrape_pubmed_ingredients.py --limit 100")
        print("  python scrape_pubmed_ingredients.py --all")
        return

    # Get ingredients
    ingredients = get_webflow_ingredients(limit)
    print()

    # Prepare output
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        'name',
        'inci_name',
        'search_variant_used',
        'pubmed_total_results',
        'research_level',
        'recent_papers_count',
        'has_recent_research',
        'top_paper_1_title',
        'top_paper_1_journal',
        'top_paper_1_year',
        'top_paper_2_title',
        'top_paper_2_journal',
        'top_paper_2_year',
        'top_paper_3_title',
        'top_paper_3_journal',
        'top_paper_3_year',
        'search_term',
        'scraped_date',
    ]

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        print(f"Searching PubMed for {len(ingredients)} ingredients...")
        print()

        extensive = 0
        moderate = 0
        limited = 0
        minimal = 0

        for i, item in enumerate(ingredients, 1):
            fd = item.get('fieldData', {})
            name = fd.get('name', '')

            if not name:
                continue

            # Search PubMed
            search_result = search_pubmed(name)
            time.sleep(0.4)  # Rate limit: max 3 requests/second without API key

            # Get paper summaries if we have results
            summaries = []
            if search_result['paper_ids']:
                summaries = get_paper_summaries(search_result['paper_ids'])
                time.sleep(0.4)

            # Categorize
            category = categorize_research(search_result['total_results'], summaries)

            # Track stats
            if category['research_level'] == 'extensive':
                extensive += 1
            elif category['research_level'] == 'moderate':
                moderate += 1
            elif category['research_level'] == 'limited':
                limited += 1
            else:
                minimal += 1

            # Build row
            row = {
                'name': name,
                'inci_name': clean_ingredient_name(name),
                'search_variant_used': search_result.get('variant_used', ''),
                'pubmed_total_results': search_result['total_results'],
                'research_level': category['research_level'],
                'recent_papers_count': category['recent_papers'],
                'has_recent_research': category['has_recent_research'],
                'search_term': search_result['search_term'],
                'scraped_date': datetime.now().isoformat(),
            }

            # Add top papers
            for j, summary in enumerate(summaries[:3], 1):
                row[f'top_paper_{j}_title'] = summary.get('title', '')
                row[f'top_paper_{j}_journal'] = summary.get('source', '')
                row[f'top_paper_{j}_year'] = summary.get('pubdate', '')

            writer.writerow(row)

            # Progress
            if i <= 10 or i % 50 == 0:
                print(f"[{i}/{len(ingredients)}] {name[:40]}")
                print(f"  PubMed results: {search_result['total_results']} ({category['research_level']})")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Ingredients searched: {len(ingredients)}")
    print()
    print("Research Level Distribution:")
    print(f"  Extensive (100+ papers): {extensive}")
    print(f"  Moderate (20-99 papers): {moderate}")
    print(f"  Limited (5-19 papers):   {limited}")
    print(f"  Minimal (<5 papers):     {minimal}")
    print()
    print(f"Output saved to: {OUTPUT_CSV}")


if __name__ == '__main__':
    main()
