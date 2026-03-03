#!/usr/bin/env python3
"""
Scrape PubMed Central full-text articles for ingredient research.

Fetches full article content when available from PMC (open access).
Falls back to abstracts when full text isn't available.

Extracts:
- Full text from PMC articles
- Key sections: Results, Conclusions, Discussion
- Efficacy data, safety findings, mechanisms
- Tables and figures descriptions when available

Usage:
    python scrape_pubmed_fulltext.py --limit 50
    python scrape_pubmed_fulltext.py --all
"""

import os
import sys
import time
import csv
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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

# PubMed/PMC E-utilities endpoints
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ELINK_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
PMC_OA_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"

# Webflow API
WEBFLOW_API_BASE = "https://api.webflow.com/v2"
INGREDIENTS_COLLECTION_ID = "67b25dbc040723aed519bf6f"

# Output files
OUTPUT_CSV = Path(__file__).parent / 'data' / 'pubmed_ingredient_fulltext.csv'
OUTPUT_JSON = Path(__file__).parent / 'data' / 'pubmed_ingredient_fulltext.json'


def clean_ingredient_name(name: str) -> str:
    """Clean ingredient name for search."""
    name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    name = ' '.join(name.split())
    return name.strip()


def clean_text_for_csv(text: str) -> str:
    """Clean text for CSV by removing newlines and excess whitespace."""
    if not text:
        return ''
    # Replace newlines and tabs with spaces
    text = re.sub(r'[\n\r\t]+', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r' +', ' ', text)
    return text.strip()


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

    # Deduplicate
    seen = set()
    unique = []
    for v in variants:
        v_lower = v.lower()
        if v_lower not in seen and len(v) > 2:
            seen.add(v_lower)
            unique.append(v)

    return unique


def search_pubmed_with_pmc(ingredient_name: str, max_results: int = 10) -> Dict:
    """
    Search PubMed for ingredient, prioritizing articles with PMC full text.
    """
    variants = extract_search_variants(ingredient_name)

    best_result = {
        'total_results': 0,
        'paper_ids': [],
        'pmc_ids': [],
        'search_term': '',
        'variant_used': '',
    }

    for variant in variants:
        # Search with open access filter to prioritize PMC articles
        query = f'"{variant}"[Title/Abstract] AND (cosmetic[Title/Abstract] OR skincare[Title/Abstract] OR "topical application"[Title/Abstract] OR dermatological[Title/Abstract]) AND "open access"[filter]'

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

            if ids:
                best_result = {
                    'total_results': total,
                    'paper_ids': ids,
                    'pmc_ids': [],
                    'search_term': query,
                    'variant_used': variant,
                }
                break

            time.sleep(0.35)

        except Exception:
            continue

    # If no open access results, try without filter
    if not best_result['paper_ids']:
        for variant in variants:
            query = f'"{variant}"[Title/Abstract] AND (cosmetic[Title/Abstract] OR skincare[Title/Abstract] OR "topical application"[Title/Abstract] OR dermatological[Title/Abstract])'

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

                if ids:
                    best_result = {
                        'total_results': total,
                        'paper_ids': ids,
                        'pmc_ids': [],
                        'search_term': query,
                        'variant_used': variant,
                    }
                    break

                time.sleep(0.35)

            except Exception:
                continue

    # Get PMC IDs for the papers
    if best_result['paper_ids']:
        pmc_ids = get_pmc_ids(best_result['paper_ids'])
        best_result['pmc_ids'] = pmc_ids

    return best_result


def get_pmc_ids(pmids: List[str]) -> List[str]:
    """Convert PubMed IDs to PMC IDs where available."""
    if not pmids:
        return []

    params = {
        'dbfrom': 'pubmed',
        'db': 'pmc',
        'id': ','.join(pmids),
        'retmode': 'json',
    }

    try:
        resp = requests.get(ELINK_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        pmc_ids = []
        linksets = data.get('linksets', [])
        for linkset in linksets:
            links = linkset.get('linksetdbs', [])
            for link in links:
                if link.get('dbto') == 'pmc':
                    pmc_ids.extend([str(lid) for lid in link.get('links', [])])

        return pmc_ids

    except Exception as e:
        return []


def fetch_pmc_fulltext(pmc_id: str) -> Dict:
    """Fetch full text from PubMed Central."""
    params = {
        'db': 'pmc',
        'id': pmc_id,
        'rettype': 'xml',
        'retmode': 'xml',
    }

    try:
        resp = requests.get(EFETCH_URL, params=params, timeout=60)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)

        article = {
            'pmc_id': pmc_id,
            'title': '',
            'abstract': '',
            'introduction': '',
            'methods': '',
            'results': '',
            'discussion': '',
            'conclusions': '',
            'full_text': '',
            'tables': [],
            'figures': [],
            'keywords': [],
            'journal': '',
            'year': '',
            'authors': '',
        }

        # Title
        title = root.find('.//article-title')
        if title is not None:
            article['title'] = ''.join(title.itertext())

        # Journal
        journal = root.find('.//journal-title')
        if journal is not None:
            article['journal'] = journal.text or ''

        # Year
        year = root.find('.//pub-date/year')
        if year is not None:
            article['year'] = year.text or ''

        # Authors
        authors = []
        for contrib in root.findall('.//contrib[@contrib-type="author"]')[:5]:
            surname = contrib.find('.//surname')
            given = contrib.find('.//given-names')
            if surname is not None:
                name = surname.text or ''
                if given is not None and given.text:
                    name = f"{given.text} {name}"
                authors.append(name)
        article['authors'] = '; '.join(authors)

        # Abstract
        abstract_elem = root.find('.//abstract')
        if abstract_elem is not None:
            article['abstract'] = ' '.join(abstract_elem.itertext())

        # Keywords
        for kwd in root.findall('.//kwd'):
            if kwd.text:
                article['keywords'].append(kwd.text)

        # Body sections
        body = root.find('.//body')
        if body is not None:
            full_text_parts = []

            for sec in body.findall('.//sec'):
                sec_type = sec.get('sec-type', '').lower()
                title_elem = sec.find('title')
                sec_title = (title_elem.text or '').lower() if title_elem is not None else ''

                # Get section text
                sec_text = ' '.join(sec.itertext())
                full_text_parts.append(sec_text)

                # Categorize by section
                if 'intro' in sec_type or 'intro' in sec_title or 'background' in sec_title:
                    article['introduction'] += sec_text + ' '
                elif 'method' in sec_type or 'method' in sec_title or 'material' in sec_title:
                    article['methods'] += sec_text + ' '
                elif 'result' in sec_type or 'result' in sec_title or 'finding' in sec_title:
                    article['results'] += sec_text + ' '
                elif 'discuss' in sec_type or 'discuss' in sec_title:
                    article['discussion'] += sec_text + ' '
                elif 'conclu' in sec_type or 'conclu' in sec_title or 'summary' in sec_title:
                    article['conclusions'] += sec_text + ' '

            article['full_text'] = ' '.join(full_text_parts)

        # Tables - extract captions and content
        for table_wrap in root.findall('.//table-wrap'):
            caption = table_wrap.find('.//caption')
            if caption is not None:
                article['tables'].append(''.join(caption.itertext()))

        # Figures - extract captions
        for fig in root.findall('.//fig'):
            caption = fig.find('.//caption')
            if caption is not None:
                article['figures'].append(''.join(caption.itertext()))

        return article

    except Exception as e:
        return {'pmc_id': pmc_id, 'error': str(e)}


def fetch_pubmed_abstract(pmid: str) -> Dict:
    """Fetch abstract from PubMed (fallback when no PMC full text)."""
    params = {
        'db': 'pubmed',
        'id': pmid,
        'retmode': 'xml',
        'rettype': 'abstract',
    }

    try:
        resp = requests.get(EFETCH_URL, params=params, timeout=30)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)

        paper = {
            'pmid': pmid,
            'title': '',
            'abstract': '',
            'journal': '',
            'year': '',
            'authors': '',
            'keywords': [],
            'mesh_terms': [],
        }

        article = root.find('.//PubmedArticle')
        if article is None:
            return paper

        # Title
        title = article.find('.//ArticleTitle')
        if title is not None:
            paper['title'] = ''.join(title.itertext())

        # Journal
        journal = article.find('.//Journal/Title')
        if journal is not None:
            paper['journal'] = journal.text or ''

        # Year
        year = article.find('.//PubDate/Year')
        if year is None:
            year = article.find('.//PubDate/MedlineDate')
        if year is not None and year.text:
            paper['year'] = year.text[:4]

        # Authors
        authors = []
        for author in article.findall('.//Author')[:5]:
            lastname = author.find('LastName')
            forename = author.find('ForeName')
            if lastname is not None:
                name = lastname.text or ''
                if forename is not None and forename.text:
                    name = f"{forename.text} {name}"
                authors.append(name)
        paper['authors'] = '; '.join(authors)

        # Abstract
        abstract_parts = []
        for abstract_text in article.findall('.//AbstractText'):
            label = abstract_text.get('Label', '')
            text = ''.join(abstract_text.itertext())
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        paper['abstract'] = ' '.join(abstract_parts)

        # Keywords
        for kw in article.findall('.//Keyword'):
            if kw.text:
                paper['keywords'].append(kw.text)

        # MeSH terms
        for mesh in article.findall('.//MeshHeading/DescriptorName'):
            if mesh.text:
                paper['mesh_terms'].append(mesh.text)

        return paper

    except Exception as e:
        return {'pmid': pmid, 'error': str(e)}


def extract_ingredient_data(text: str, ingredient_name: str) -> Dict:
    """
    Extract structured data about the ingredient from article text.
    """
    data = {
        'efficacy_findings': [],
        'safety_findings': [],
        'mechanisms': [],
        'skin_benefits': [],
        'concentrations': [],
        'study_results': [],
        'formulations': [],
    }

    if not text:
        return data

    text_lower = text.lower()

    # Concentration patterns (e.g., "0.5%", "1 mg/mL")
    conc_patterns = [
        r'(\d+(?:\.\d+)?)\s*%',
        r'(\d+(?:\.\d+)?)\s*(?:mg|g|mcg|µg)/(?:ml|mL|L|g|kg)',
        r'(\d+(?:\.\d+)?)\s*(?:ppm|ppb)',
    ]
    for pattern in conc_patterns:
        matches = re.findall(pattern, text)
        data['concentrations'].extend(matches[:5])

    # Efficacy/result patterns
    efficacy_patterns = [
        r'(?:significant(?:ly)?|marked(?:ly)?)\s+(?:improve|reduc|increas|decreas|enhanc)[a-z]*\s+(?:in\s+)?([^.]{10,100})',
        r'(?:result(?:ed|s|ing)?|showed?|demonstrat|reveal)[a-z]*\s+(?:that\s+)?([^.]{10,100})',
        r'(?:\d+(?:\.\d+)?%)\s+(?:improve|reduc|increas|decreas)[a-z]*\s+(?:in\s+)?([^.]{10,80})',
    ]
    for pattern in efficacy_patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches[:5]:
            if len(match) > 15:
                data['efficacy_findings'].append(match.strip().capitalize())

    # Safety patterns
    safety_patterns = [
        r'(?:safe|well[- ]tolerat|non[- ]?toxic)[a-z]*[^.]{0,50}',
        r'(?:no\s+(?:significant\s+)?(?:adverse|side|toxic|irritat))[^.]{0,80}',
        r'(?:irritat|sensitiz|allerg|phototoxic|cytotoxic)[a-z]*[^.]{0,80}',
        r'(?:ld50|ic50|ec50)[^.]{0,60}',
    ]
    for pattern in safety_patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches[:3]:
            if len(match) > 10:
                data['safety_findings'].append(match.strip().capitalize())

    # Mechanism patterns
    mechanism_patterns = [
        r'(?:inhibit|activat|modulat|regulat|suppress|stimulat)[a-z]*\s+(?:the\s+)?(?:expression\s+of\s+)?([A-Za-z0-9\-]+(?:\s+[a-z]+){0,3})',
        r'(?:via|through|by)\s+(?:the\s+)?([A-Za-z0-9\-/]+)\s+(?:pathway|signaling|mechanism)',
        r'(?:downregulat|upregulat)[a-z]*\s+([A-Za-z0-9\-]+)',
    ]
    for pattern in mechanism_patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches[:5]:
            if len(match) > 2:
                data['mechanisms'].append(match.strip())

    # Skin benefit patterns
    benefit_keywords = {
        'anti-aging': ['anti[- ]?aging', 'antiaging', 'anti[- ]?wrinkle', 'wrinkle reduction'],
        'antioxidant': ['antioxidant', 'free radical', 'oxidative stress', 'ros scaveng'],
        'anti-inflammatory': ['anti[- ]?inflammat', 'inflammat.*reduc', 'cytokine.*inhibit'],
        'moisturizing': ['moisturiz', 'hydrat', 'water retention', 'skin hydration', 'tewl'],
        'brightening': ['brighten', 'lighten', 'whitening', 'depigment', 'melanin.*inhibit', 'tyrosinase.*inhibit'],
        'collagen': ['collagen.*synthes', 'collagen.*product', 'procollagen', 'collagen.*stimulat'],
        'wound healing': ['wound heal', 'tissue repair', 'epithelializ', 'regenerat'],
        'antimicrobial': ['antimicrob', 'antibacter', 'antifung', 'antiseptic'],
        'UV protection': ['uv protect', 'sun protect', 'spf', 'photoprotect'],
        'acne': ['acne', 'sebum.*reduc', 'comedone', 'p\\.? ?acnes'],
        'elasticity': ['elasticity', 'elastin', 'skin firm', 'skin tight'],
        'barrier': ['skin barrier', 'barrier function', 'barrier repair', 'ceramide'],
    }

    for benefit, patterns in benefit_keywords.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                if benefit not in data['skin_benefits']:
                    data['skin_benefits'].append(benefit)
                break

    # Formulation patterns
    formulation_patterns = [
        r'(?:cream|lotion|serum|gel|emulsion|ointment|mask|toner)\s+(?:formulation|containing|with)',
        r'(?:liposome|nanoparticle|microemulsion|nanoemulsion)[a-z]*',
        r'(?:topical|transdermal)\s+(?:delivery|application|formulation)',
    ]
    for pattern in formulation_patterns:
        matches = re.findall(pattern, text_lower)
        data['formulations'].extend(matches[:3])

    # Deduplicate
    for key in data:
        data[key] = list(dict.fromkeys(data[key]))[:10]

    return data


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
    print("PUBMED FULL-TEXT INGREDIENT SCRAPER")
    print("=" * 70)
    print()

    args = sys.argv[1:]
    limit = None

    for i, arg in enumerate(args):
        if arg == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1])

    if '--all' not in args and limit is None:
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
        'has_fulltext',
        'skin_benefits',
        'efficacy_findings',
        'safety_findings',
        'mechanisms',
        'concentrations_tested',
        'formulations',
        'study_types',
        'paper_1_title',
        'paper_1_journal',
        'paper_1_year',
        'paper_1_results_excerpt',
        'paper_2_title',
        'paper_2_journal',
        'paper_2_year',
        'paper_2_results_excerpt',
        'paper_3_title',
        'paper_3_journal',
        'paper_3_year',
        'paper_3_results_excerpt',
        'all_keywords',
        'search_term',
        'scraped_date',
    ]

    # Also save detailed JSON
    all_data = []

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        print(f"Searching PubMed/PMC for {len(ingredients)} ingredients...")
        print("(Fetching full text when available from PubMed Central)")
        print()

        stats = {'extensive': 0, 'moderate': 0, 'limited': 0, 'minimal': 0, 'fulltext': 0}

        for i, item in enumerate(ingredients, 1):
            fd = item.get('fieldData', {})
            name = fd.get('name', '')

            if not name:
                continue

            # Search PubMed
            search_result = search_pubmed_with_pmc(name)
            time.sleep(0.4)

            papers = []
            combined_data = {
                'skin_benefits': [],
                'efficacy_findings': [],
                'safety_findings': [],
                'mechanisms': [],
                'concentrations': [],
                'formulations': [],
                'study_types': [],
                'keywords': [],
            }

            has_fulltext = False

            # Try to fetch PMC full text first
            for pmc_id in search_result.get('pmc_ids', [])[:3]:
                article = fetch_pmc_fulltext(pmc_id)
                time.sleep(0.5)

                if article.get('full_text') or article.get('results'):
                    has_fulltext = True
                    stats['fulltext'] += 1

                    # Extract data from full text
                    text_to_analyze = article.get('results', '') + ' ' + article.get('discussion', '') + ' ' + article.get('conclusions', '')
                    extracted = extract_ingredient_data(text_to_analyze, name)

                    # Merge extracted data
                    for key in combined_data:
                        if key in extracted:
                            combined_data[key].extend(extracted[key])

                    combined_data['keywords'].extend(article.get('keywords', []))

                    papers.append({
                        'title': clean_text_for_csv(article.get('title', '')),
                        'journal': article.get('journal', ''),
                        'year': article.get('year', ''),
                        'type': 'Full Text (PMC)',
                        'results_excerpt': clean_text_for_csv((article.get('results', '') or article.get('conclusions', ''))[:1500]),
                    })

                    if len(papers) >= 3:
                        break

            # Fill remaining with abstracts
            if len(papers) < 3:
                for pmid in search_result.get('paper_ids', []):
                    if len(papers) >= 3:
                        break

                    # Skip if we already got this as full text
                    abstract = fetch_pubmed_abstract(pmid)
                    time.sleep(0.4)

                    if abstract.get('title') and not any(p['title'] == abstract['title'] for p in papers):
                        # Extract data from abstract
                        extracted = extract_ingredient_data(abstract.get('abstract', ''), name)

                        for key in combined_data:
                            if key in extracted:
                                combined_data[key].extend(extracted[key])

                        combined_data['keywords'].extend(abstract.get('keywords', []))
                        combined_data['keywords'].extend(abstract.get('mesh_terms', []))

                        papers.append({
                            'title': clean_text_for_csv(abstract.get('title', '')),
                            'journal': abstract.get('journal', ''),
                            'year': abstract.get('year', ''),
                            'type': 'Abstract',
                            'results_excerpt': clean_text_for_csv(abstract.get('abstract', '')[:1500]),
                        })

            # Deduplicate combined data
            for key in combined_data:
                combined_data[key] = list(dict.fromkeys(combined_data[key]))[:15]

            # Categorize
            research_level = categorize_research(search_result['total_results'])
            stats[research_level] += 1

            # Build CSV row - clean all text fields to remove newlines
            row = {
                'name': name,
                'inci_name': clean_ingredient_name(name),
                'search_variant_used': search_result.get('variant_used', ''),
                'pubmed_total_results': search_result['total_results'],
                'research_level': research_level,
                'has_fulltext': has_fulltext,
                'skin_benefits': '; '.join(combined_data['skin_benefits']),
                'efficacy_findings': clean_text_for_csv('; '.join(combined_data['efficacy_findings'][:5])),
                'safety_findings': clean_text_for_csv('; '.join(combined_data['safety_findings'][:5])),
                'mechanisms': clean_text_for_csv('; '.join(combined_data['mechanisms'][:5])),
                'concentrations_tested': '; '.join(combined_data['concentrations'][:5]),
                'formulations': clean_text_for_csv('; '.join(combined_data['formulations'][:3])),
                'study_types': '; '.join(set(p['type'] for p in papers)),
                'all_keywords': clean_text_for_csv('; '.join(combined_data['keywords'][:15])),
                'search_term': search_result['search_term'],
                'scraped_date': datetime.now().isoformat(),
            }

            # Add individual papers
            for j, paper in enumerate(papers[:3], 1):
                row[f'paper_{j}_title'] = clean_text_for_csv(paper.get('title', ''))
                row[f'paper_{j}_journal'] = paper.get('journal', '')
                row[f'paper_{j}_year'] = paper.get('year', '')
                row[f'paper_{j}_results_excerpt'] = clean_text_for_csv(paper.get('results_excerpt', ''))[:2000]

            writer.writerow(row)

            # Save detailed JSON
            all_data.append({
                'name': name,
                'inci_name': clean_ingredient_name(name),
                'search_result': search_result,
                'combined_data': combined_data,
                'papers': papers,
                'research_level': research_level,
                'scraped_date': datetime.now().isoformat(),
            })

            # Progress
            if i <= 10 or i % 25 == 0:
                ft_tag = "[FULL TEXT]" if has_fulltext else "[abstract]"
                benefits = '; '.join(combined_data['skin_benefits'][:3]) or 'none found'
                print(f"[{i}/{len(ingredients)}] {name[:30]}")
                print(f"  {ft_tag} Papers: {search_result['total_results']} | Benefits: {benefits}")

    # Save JSON
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Ingredients searched: {len(ingredients)}")
    print(f"Full-text articles found: {stats['fulltext']}")
    print()
    print("Research Level Distribution:")
    print(f"  Extensive (100+ papers): {stats['extensive']}")
    print(f"  Moderate (20-99 papers): {stats['moderate']}")
    print(f"  Limited (5-19 papers):   {stats['limited']}")
    print(f"  Minimal (<5 papers):     {stats['minimal']}")
    print()
    print(f"CSV output: {OUTPUT_CSV}")
    print(f"JSON output: {OUTPUT_JSON}")


if __name__ == '__main__':
    main()
