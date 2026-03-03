#!/usr/bin/env python3
"""
Scrape PubMed abstracts and extract key findings for ingredients.

This script enriches ingredient data with actual research content:
- Fetches full abstracts from PubMed
- Extracts key findings about efficacy, safety, and mechanisms
- Can run on existing CSV or fresh from Webflow

Usage:
    python scrape_pubmed_abstracts.py --limit 50
    python scrape_pubmed_abstracts.py --all
    python scrape_pubmed_abstracts.py --enrich existing_csv.csv
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
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Webflow API
WEBFLOW_API_BASE = "https://api.webflow.com/v2"
INGREDIENTS_COLLECTION_ID = "67b25dbc040723aed519bf6f"

# Output file
OUTPUT_CSV = Path(__file__).parent / 'data' / 'pubmed_ingredient_abstracts.csv'


def clean_ingredient_name(name: str) -> str:
    """Clean ingredient name for PubMed search."""
    name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    name = ' '.join(name.split())
    return name.strip()


def extract_search_variants(name: str) -> List[str]:
    """Extract multiple search variants from an ingredient name."""
    variants = []

    clean = clean_ingredient_name(name)
    variants.append(clean)

    # Extract common name from parentheses
    match = re.search(r'\(([^)]+)\)', name)
    if match:
        common_name = match.group(1).strip()
        if common_name and len(common_name) > 2:
            variants.append(common_name)

    # Extract genus
    words = clean.split()
    if len(words) >= 2 and words[0][0].isupper():
        genus = words[0]
        if len(genus) > 3:
            variants.append(genus)

    # Remove qualifiers
    qualifiers = ['root', 'leaf', 'seed', 'flower', 'bark', 'fruit', 'oil', 'extract',
                  'powder', 'juice', 'water', 'butter', 'wax', 'cell', 'culture']
    base_name = clean.lower()
    for q in qualifiers:
        base_name = re.sub(rf'\b{q}\b', '', base_name)
    base_name = ' '.join(base_name.split()).strip()
    if base_name and base_name != clean.lower() and len(base_name) > 3:
        variants.append(base_name.title())

    # Remove duplicates
    seen = set()
    unique = []
    for v in variants:
        v_lower = v.lower()
        if v_lower not in seen and len(v) > 2:
            seen.add(v_lower)
            unique.append(v)

    return unique


def search_pubmed(ingredient_name: str, max_results: int = 10) -> Dict:
    """Search PubMed for an ingredient, focused on topical/cosmetic use."""
    variants = extract_search_variants(ingredient_name)

    best_result = {
        'total_results': 0,
        'paper_ids': [],
        'search_term': '',
        'variant_used': '',
    }

    all_results = []

    for variant in variants:
        # Focus on cosmetic/topical/dermatological research
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

            if 5 <= total <= 500:
                best_result = all_results[-1]
                break

            time.sleep(0.35)

        except Exception as e:
            continue

    if best_result['total_results'] == 0 and all_results:
        for r in all_results:
            if 1 <= r['total_results'] <= 1000:
                best_result = r
                break
        if best_result['total_results'] == 0:
            for r in all_results:
                if r['total_results'] > 0:
                    best_result = r
                    break

    if not best_result['search_term']:
        best_result['search_term'] = f'"{variants[0]}"[Title/Abstract]' if variants else ingredient_name

    return best_result


def fetch_abstracts(paper_ids: List[str]) -> List[Dict]:
    """Fetch full abstracts for a list of PubMed IDs."""
    if not paper_ids:
        return []

    params = {
        'db': 'pubmed',
        'id': ','.join(paper_ids[:5]),  # Limit to 5 papers for detail
        'retmode': 'xml',
        'rettype': 'abstract',
    }

    try:
        resp = requests.get(EFETCH_URL, params=params, timeout=30)
        resp.raise_for_status()

        # Parse XML response
        root = ET.fromstring(resp.content)

        papers = []
        for article in root.findall('.//PubmedArticle'):
            paper = {}

            # PMID
            pmid = article.find('.//PMID')
            paper['pmid'] = pmid.text if pmid is not None else ''

            # Title
            title = article.find('.//ArticleTitle')
            paper['title'] = title.text if title is not None else ''

            # Journal
            journal = article.find('.//Journal/Title')
            paper['journal'] = journal.text if journal is not None else ''

            # Year
            year = article.find('.//PubDate/Year')
            if year is None:
                year = article.find('.//PubDate/MedlineDate')
            paper['year'] = year.text[:4] if year is not None and year.text else ''

            # Abstract - combine all abstract text sections
            abstract_parts = []
            for abstract_text in article.findall('.//AbstractText'):
                label = abstract_text.get('Label', '')
                text = ''.join(abstract_text.itertext())
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            paper['abstract'] = ' '.join(abstract_parts)

            # Authors (first 3)
            authors = []
            for author in article.findall('.//Author')[:3]:
                lastname = author.find('LastName')
                forename = author.find('ForeName')
                if lastname is not None:
                    name = lastname.text
                    if forename is not None:
                        name = f"{forename.text} {name}"
                    authors.append(name)
            paper['authors'] = '; '.join(authors)

            # Keywords
            keywords = []
            for kw in article.findall('.//Keyword'):
                if kw.text:
                    keywords.append(kw.text)
            paper['keywords'] = '; '.join(keywords[:10])

            # MeSH terms
            mesh_terms = []
            for mesh in article.findall('.//MeshHeading/DescriptorName'):
                if mesh.text:
                    mesh_terms.append(mesh.text)
            paper['mesh_terms'] = '; '.join(mesh_terms[:10])

            papers.append(paper)

        return papers

    except Exception as e:
        print(f"  Abstract fetch error: {e}")
        return []


def extract_key_findings(abstract: str, ingredient_name: str) -> Dict:
    """
    Extract key findings from abstract text.
    Returns structured data about efficacy, safety, and mechanisms.
    """
    findings = {
        'efficacy_claims': [],
        'safety_notes': [],
        'mechanisms': [],
        'skin_benefits': [],
        'study_type': '',
    }

    if not abstract:
        return findings

    abstract_lower = abstract.lower()

    # Detect study type
    if any(term in abstract_lower for term in ['randomized', 'double-blind', 'placebo-controlled', 'clinical trial']):
        findings['study_type'] = 'Clinical Trial'
    elif any(term in abstract_lower for term in ['in vitro', 'cell culture', 'cultured cells']):
        findings['study_type'] = 'In Vitro'
    elif any(term in abstract_lower for term in ['in vivo', 'animal model', 'mice', 'rats']):
        findings['study_type'] = 'In Vivo (Animal)'
    elif any(term in abstract_lower for term in ['review', 'systematic review', 'meta-analysis']):
        findings['study_type'] = 'Review'
    elif any(term in abstract_lower for term in ['human subjects', 'volunteers', 'participants']):
        findings['study_type'] = 'Human Study'

    # Efficacy patterns
    efficacy_patterns = [
        (r'(?:significant(?:ly)?|marked(?:ly)?|substantial(?:ly)?)\s+(?:improve|reduce|increase|decrease|enhance)[sd]?\s+([^.]{10,80})', 'efficacy_claims'),
        (r'(?:effective|efficacious)\s+(?:in|for|at)\s+([^.]{10,80})', 'efficacy_claims'),
        (r'(?:inhibit|suppress|prevent)[sd]?\s+([^.]{10,60})', 'efficacy_claims'),
    ]

    # Skin benefit patterns
    benefit_patterns = [
        (r'anti[- ]?(?:aging|wrinkle|oxidant|inflammatory|microbial|bacterial|fungal)', 'skin_benefits'),
        (r'(?:moisturiz|hydrat|soften|smooth|firm|brighten|lighten|whiten)[eing]+', 'skin_benefits'),
        (r'(?:collagen|elastin|hyaluronic)\s+(?:synthesis|production|stimulation)', 'skin_benefits'),
        (r'(?:wound|skin)\s+healing', 'skin_benefits'),
        (r'(?:uv|sun)\s*(?:protection|protective|filter)', 'skin_benefits'),
        (r'(?:acne|pigmentation|hyperpigmentation|melasma|wrinkle|fine line)[s]?\s+(?:reduction|treatment|improvement)', 'skin_benefits'),
    ]

    # Safety patterns
    safety_patterns = [
        (r'(?:safe|well[- ]tolerated|non[- ]?toxic|no adverse)', 'safety_notes'),
        (r'(?:irritation|sensitization|allergy|allergic|phototoxic|cytotoxic)', 'safety_notes'),
        (r'(?:side effect|adverse event|contraindication)', 'safety_notes'),
    ]

    # Mechanism patterns
    mechanism_patterns = [
        (r'(?:mechanism|pathway|mediat)[^.]{5,80}(?:through|via|by)[^.]{5,60}', 'mechanisms'),
        (r'(?:activat|inhibit|regulat|modulat)[es]?\s+(?:the\s+)?([A-Z0-9][^.]{5,50})', 'mechanisms'),
    ]

    # Extract matches
    for pattern, category in efficacy_patterns + benefit_patterns + safety_patterns + mechanism_patterns:
        matches = re.findall(pattern, abstract_lower, re.IGNORECASE)
        for match in matches[:3]:  # Limit matches
            if isinstance(match, str) and len(match) > 5:
                clean_match = match.strip().capitalize()
                if clean_match not in findings[category]:
                    findings[category].append(clean_match)

    return findings


def summarize_findings(papers: List[Dict], ingredient_name: str) -> Dict:
    """Summarize findings across multiple papers for an ingredient."""
    summary = {
        'total_papers_analyzed': len(papers),
        'study_types': [],
        'all_efficacy_claims': [],
        'all_safety_notes': [],
        'all_skin_benefits': [],
        'all_mechanisms': [],
        'key_journals': [],
        'year_range': '',
        'combined_abstract_excerpt': '',
    }

    years = []
    for paper in papers:
        # Extract findings from each paper
        findings = extract_key_findings(paper.get('abstract', ''), ingredient_name)

        if findings['study_type']:
            summary['study_types'].append(findings['study_type'])
        summary['all_efficacy_claims'].extend(findings['efficacy_claims'])
        summary['all_safety_notes'].extend(findings['safety_notes'])
        summary['all_skin_benefits'].extend(findings['skin_benefits'])
        summary['all_mechanisms'].extend(findings['mechanisms'])

        if paper.get('journal'):
            summary['key_journals'].append(paper['journal'])

        if paper.get('year'):
            try:
                years.append(int(paper['year']))
            except:
                pass

    # Deduplicate and limit
    summary['study_types'] = list(set(summary['study_types']))[:5]
    summary['all_efficacy_claims'] = list(set(summary['all_efficacy_claims']))[:10]
    summary['all_safety_notes'] = list(set(summary['all_safety_notes']))[:5]
    summary['all_skin_benefits'] = list(set(summary['all_skin_benefits']))[:10]
    summary['all_mechanisms'] = list(set(summary['all_mechanisms']))[:5]
    summary['key_journals'] = list(set(summary['key_journals']))[:5]

    if years:
        summary['year_range'] = f"{min(years)}-{max(years)}"

    # Combine first ~500 chars of abstracts
    combined = []
    for paper in papers[:3]:
        abstract = paper.get('abstract', '')
        if abstract:
            combined.append(abstract[:300])
    summary['combined_abstract_excerpt'] = ' [...] '.join(combined)[:1000]

    return summary


def categorize_research(total_results: int) -> str:
    """Categorize research level."""
    if total_results >= 100:
        return 'extensive'
    elif total_results >= 20:
        return 'moderate'
    elif total_results >= 5:
        return 'limited'
    else:
        return 'minimal'


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

        time.sleep(0.5)

    print(f"  Loaded {len(items)} ingredients total")
    return items


def main():
    print("=" * 70)
    print("PUBMED INGREDIENT ABSTRACTS SCRAPER")
    print("=" * 70)
    print()

    args = sys.argv[1:]
    limit = None
    enrich_file = None

    for i, arg in enumerate(args):
        if arg == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1])
        elif arg == '--enrich' and i + 1 < len(args):
            enrich_file = args[i + 1]

    if '--all' not in args and limit is None and enrich_file is None:
        print(__doc__)
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
        'papers_analyzed',
        'study_types',
        'skin_benefits',
        'efficacy_claims',
        'safety_notes',
        'mechanisms',
        'key_journals',
        'year_range',
        'paper_1_title',
        'paper_1_abstract',
        'paper_2_title',
        'paper_2_abstract',
        'paper_3_title',
        'paper_3_abstract',
        'combined_excerpt',
        'search_term',
        'scraped_date',
    ]

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        print(f"Searching PubMed and fetching abstracts for {len(ingredients)} ingredients...")
        print()

        stats = {'extensive': 0, 'moderate': 0, 'limited': 0, 'minimal': 0}

        for i, item in enumerate(ingredients, 1):
            fd = item.get('fieldData', {})
            name = fd.get('name', '')

            if not name:
                continue

            # Search PubMed
            search_result = search_pubmed(name)
            time.sleep(0.4)

            # Fetch abstracts if we have results
            papers = []
            summary = {}
            if search_result['paper_ids']:
                papers = fetch_abstracts(search_result['paper_ids'])
                time.sleep(0.4)

                # Summarize findings
                summary = summarize_findings(papers, name)

            # Categorize
            research_level = categorize_research(search_result['total_results'])
            stats[research_level] += 1

            # Build row
            row = {
                'name': name,
                'inci_name': clean_ingredient_name(name),
                'search_variant_used': search_result.get('variant_used', ''),
                'pubmed_total_results': search_result['total_results'],
                'research_level': research_level,
                'papers_analyzed': summary.get('total_papers_analyzed', 0),
                'study_types': '; '.join(summary.get('study_types', [])),
                'skin_benefits': '; '.join(summary.get('all_skin_benefits', [])),
                'efficacy_claims': '; '.join(summary.get('all_efficacy_claims', [])),
                'safety_notes': '; '.join(summary.get('all_safety_notes', [])),
                'mechanisms': '; '.join(summary.get('all_mechanisms', [])),
                'key_journals': '; '.join(summary.get('key_journals', [])),
                'year_range': summary.get('year_range', ''),
                'combined_excerpt': summary.get('combined_abstract_excerpt', ''),
                'search_term': search_result['search_term'],
                'scraped_date': datetime.now().isoformat(),
            }

            # Add individual papers
            for j, paper in enumerate(papers[:3], 1):
                row[f'paper_{j}_title'] = paper.get('title', '')
                row[f'paper_{j}_abstract'] = paper.get('abstract', '')[:2000]  # Limit abstract length

            writer.writerow(row)

            # Progress
            if i <= 10 or i % 25 == 0:
                benefits = '; '.join(summary.get('all_skin_benefits', []))[:50] if summary else ''
                print(f"[{i}/{len(ingredients)}] {name[:35]}")
                print(f"  Papers: {search_result['total_results']} ({research_level}) | Benefits: {benefits}...")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Ingredients searched: {len(ingredients)}")
    print()
    print("Research Level Distribution:")
    print(f"  Extensive (100+ papers): {stats['extensive']}")
    print(f"  Moderate (20-99 papers): {stats['moderate']}")
    print(f"  Limited (5-19 papers):   {stats['limited']}")
    print(f"  Minimal (<5 papers):     {stats['minimal']}")
    print()
    print(f"Output saved to: {OUTPUT_CSV}")


if __name__ == '__main__':
    main()
