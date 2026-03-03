"""
Find and merge duplicate ingredients based on:
1. Name variants (e.g., "Glycerin" vs "Glycerin Extract")
2. Common name matches (one ingredient's INCI name = another's listed common name)
3. CAS number matches with similar names

Usage:
    python find_and_merge_duplicates.py              # Dry run - shows what would be merged
    python find_and_merge_duplicates.py --merge      # Actually merge duplicates
    python find_and_merge_duplicates.py --safe-only  # Only merge the safest duplicates
"""

import sqlite3
import os
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Database path
DB_PATH = Path(__file__).parent.parent / 'data' / 'ingredients.db'

# Suffixes that typically indicate the same base ingredient
EQUIVALENT_SUFFIXES = {
    ' extract': 1.0,        # Very likely same ingredient
    ' powder': 0.9,         # Usually same, just dried
    ' gum': 0.8,           # Usually same source
    ' water': 0.7,         # Could be different (hydrosol vs extract)
}

# Suffixes that indicate potentially different products
DIFFERENT_FORM_SUFFIXES = {' oil', ' butter', ' wax', ' juice'}


def score_completeness(ing: dict) -> int:
    """Score how complete an ingredient record is (higher = better to keep)."""
    score = 0

    # EWG data is valuable
    if ing.get('ewg_score') is not None:
        score += 10
    if ing.get('ewg_url'):
        score += 5

    # CIR safety data
    if ing.get('cir_safety'):
        score += 8

    # PubChem data
    if ing.get('pubchem_cid'):
        score += 5
    if ing.get('molecular_formula'):
        score += 3

    # Description and function
    if ing.get('description') and len(ing['description']) > 20:
        score += 5
    if ing.get('function'):
        score += 3

    # Botanical data
    if ing.get('plant_family'):
        score += 2
    if ing.get('plant_part'):
        score += 2

    # Webflow sync status
    if ing.get('webflow_id'):
        score += 3

    # Common names (more = better documented)
    common = ing.get('common_names') or ''
    if common:
        score += min(5, len(common.split(',')))

    # Prefer shorter, cleaner INCI names (standard format)
    name = ing.get('inci_name', '')
    if name and not any(x in name.lower() for x in [', ', ' extract', ' oil']):
        score += 2

    return score


def merge_ingredient_data(primary: dict, secondary: dict) -> dict:
    """
    Merge data from secondary into primary, keeping best data from each.
    Returns the merged data.
    """
    merged = dict(primary)

    # Fields where we take the first non-null value
    simple_fields = [
        'ewg_score', 'ewg_concern_level', 'ewg_data_availability', 'ewg_url', 'ewg_id',
        'cancer_concern', 'developmental_concern', 'allergy_concern', 'organ_toxicity',
        'cir_safety', 'cir_conditions', 'cir_url', 'cir_id', 'cir_year',
        'cas_number', 'ec_number', 'cosing_id',
        'pubchem_cid', 'molecular_formula', 'molecular_weight',
        'plant_family', 'plant_part', 'origin', 'process',
        'form', 'scent', 'kind',
        'persona_gentle', 'persona_skeptic', 'persona_family',
        'persona_antiaging', 'persona_genz', 'persona_inclusive',
    ]

    for field in simple_fields:
        if not merged.get(field) and secondary.get(field):
            merged[field] = secondary[field]

    # Text fields - prefer longer content
    text_fields = [
        'description', 'function', 'safety_concerns', 'contraindications',
        'aromatherapy_uses', 'medicinal_uses', 'chemistry_nutrients',
    ]

    for field in text_fields:
        primary_val = merged.get(field) or ''
        secondary_val = secondary.get(field) or ''
        if len(secondary_val) > len(primary_val):
            merged[field] = secondary_val

    # Merge common names
    primary_common = set(n.strip() for n in (merged.get('common_names') or '').split(',') if n.strip())
    secondary_common = set(n.strip() for n in (secondary.get('common_names') or '').split(',') if n.strip())

    # Add secondary's INCI name as a common name
    secondary_name = secondary.get('inci_name', '').strip()
    if secondary_name and secondary_name.lower() != merged['inci_name'].lower():
        primary_common.add(secondary_name)

    all_common = primary_common | secondary_common
    if all_common:
        merged['common_names'] = ','.join(sorted(all_common))

    # Banned regions - combine
    primary_banned = set(n.strip() for n in (merged.get('banned_regions') or '').split(',') if n.strip())
    secondary_banned = set(n.strip() for n in (secondary.get('banned_regions') or '').split(',') if n.strip())
    all_banned = primary_banned | secondary_banned
    if all_banned:
        merged['banned_regions'] = ','.join(sorted(all_banned))

    # Boolean flags - prefer True
    if secondary.get('is_clean'):
        merged['is_clean'] = 1
    if secondary.get('is_controversial'):
        merged['is_controversial'] = 1

    return merged


def normalize_name(name: str) -> str:
    """Normalize ingredient name for comparison."""
    return ' '.join(name.lower().strip().split())


def get_base_name(name: str) -> tuple:
    """
    Extract base name and suffix from ingredient name.
    Returns (base_name, suffix, confidence) where confidence is how likely
    the suffix indicates the same ingredient.
    """
    name_lower = name.lower().strip()

    # Check for equivalent suffixes first
    for suffix, confidence in EQUIVALENT_SUFFIXES.items():
        if name_lower.endswith(suffix):
            base = name_lower[:-len(suffix)].strip()
            return (base, suffix, confidence)

    # Check for different form suffixes
    for suffix in DIFFERENT_FORM_SUFFIXES:
        if name_lower.endswith(suffix):
            base = name_lower[:-len(suffix)].strip()
            return (base, suffix, 0.3)  # Low confidence - likely different

    return (name_lower, '', 1.0)


def find_duplicates(cursor, safe_only=False) -> list:
    """
    Find duplicate ingredient pairs.

    Categories:
    1. HIGH confidence: Same normalized name (capitalization/spacing)
    2. MEDIUM confidence: Name variants (X vs X Extract, X vs X Powder)
    3. LOW confidence: CAS matches with similar names

    Args:
        safe_only: If True, only return HIGH and MEDIUM confidence duplicates
    """
    cursor.execute('SELECT * FROM ingredients ORDER BY inci_name')
    ingredients = [dict(row) for row in cursor.fetchall()]

    # Build indices
    by_name_normalized = defaultdict(list)
    by_base_name = defaultdict(list)
    by_cas = defaultdict(list)

    for ing in ingredients:
        name = ing['inci_name']
        normalized = normalize_name(name)
        by_name_normalized[normalized].append(ing)

        base, suffix, conf = get_base_name(name)
        by_base_name[base].append((ing, suffix, conf))

        cas = (ing.get('cas_number') or '').strip()
        if cas and len(cas) > 5:
            by_cas[cas].append(ing)

    duplicates = []
    seen_pairs = set()

    # HIGH confidence: Same normalized name
    for normalized, ings in by_name_normalized.items():
        if len(ings) > 1:
            for i in range(len(ings)):
                for j in range(i + 1, len(ings)):
                    pair_key = tuple(sorted([ings[i]['id'], ings[j]['id']]))
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        duplicates.append({
                            'type': 'exact_match',
                            'confidence': 'HIGH',
                            'items': [ings[i], ings[j]],
                            'reason': f"Same name (different case/spacing)"
                        })

    # MEDIUM confidence: Name variants (X vs X Extract, etc.)
    for base, entries in by_base_name.items():
        if len(entries) > 1:
            # Group by whether they have a suffix or not
            no_suffix = [e for e in entries if not e[1]]
            with_suffix = [e for e in entries if e[1]]

            # Match base name with suffixed versions
            for base_entry in no_suffix:
                for suffixed in with_suffix:
                    pair_key = tuple(sorted([base_entry[0]['id'], suffixed[0]['id']]))
                    if pair_key not in seen_pairs:
                        # Skip if suffix indicates different form
                        if suffixed[1] in DIFFERENT_FORM_SUFFIXES:
                            continue
                        seen_pairs.add(pair_key)
                        conf = 'MEDIUM' if suffixed[2] >= 0.7 else 'LOW'
                        duplicates.append({
                            'type': 'name_variant',
                            'confidence': conf,
                            'items': [base_entry[0], suffixed[0]],
                            'reason': f"'{base_entry[0]['inci_name']}' + '{suffixed[1].strip()}' = '{suffixed[0]['inci_name']}'"
                        })

    if safe_only:
        return [d for d in duplicates if d['confidence'] in ('HIGH', 'MEDIUM')]

    # LOW confidence: CAS matches with similar names
    for cas, ings in by_cas.items():
        if len(ings) > 1:
            for i in range(len(ings)):
                for j in range(i + 1, len(ings)):
                    pair_key = tuple(sorted([ings[i]['id'], ings[j]['id']]))
                    if pair_key not in seen_pairs:
                        # Check if names share significant words
                        words1 = set(normalize_name(ings[i]['inci_name']).split())
                        words2 = set(normalize_name(ings[j]['inci_name']).split())
                        shared = words1 & words2
                        ignore = {'extract', 'oil', 'seed', 'leaf', 'flower', 'root', 'fruit', 'acid', 'the', 'and'}
                        meaningful = shared - ignore

                        if meaningful and len(meaningful) / min(len(words1), len(words2)) >= 0.3:
                            seen_pairs.add(pair_key)
                            duplicates.append({
                                'type': 'cas_match',
                                'confidence': 'LOW',
                                'items': [ings[i], ings[j]],
                                'reason': f"Same CAS ({cas}), shared words: {meaningful}"
                            })

    return duplicates


def merge_duplicates(dry_run=True, safe_only=False):
    """Find and merge duplicate ingredients."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 70)
    print("INGREDIENT DUPLICATE FINDER & MERGER")
    print("=" * 70)
    print(f"\nDatabase: {DB_PATH}")
    mode_str = 'DRY RUN' if dry_run else 'MERGE'
    if safe_only:
        mode_str += ' (SAFE ONLY - HIGH/MEDIUM confidence)'
    print(f"Mode: {mode_str}")
    print()

    # Get stats
    cursor.execute('SELECT COUNT(*) FROM ingredients')
    total = cursor.fetchone()[0]
    print(f"Total ingredients: {total}")

    # Find duplicates
    print("\nSearching for duplicates...")
    duplicates = find_duplicates(cursor, safe_only=safe_only)

    if not duplicates:
        print("No duplicates found!")
        conn.close()
        return {'merged': 0, 'found': 0}

    # Group by confidence and type
    by_confidence = defaultdict(list)
    by_type = defaultdict(list)
    for dup in duplicates:
        by_confidence[dup['confidence']].append(dup)
        by_type[dup['type']].append(dup)

    print(f"\nFound {len(duplicates)} duplicate pairs:")
    print("\nBy confidence:")
    for conf in ['HIGH', 'MEDIUM', 'LOW']:
        if conf in by_confidence:
            print(f"  - {conf}: {len(by_confidence[conf])}")
    print("\nBy type:")
    for dtype, dups in by_type.items():
        print(f"  - {dtype}: {len(dups)}")

    # Show samples by confidence
    print("\n" + "-" * 70)
    print("SAMPLE DUPLICATES BY CONFIDENCE:")
    print("-" * 70)

    shown = 0
    for conf in ['HIGH', 'MEDIUM', 'LOW']:
        conf_dups = by_confidence.get(conf, [])
        if conf_dups:
            print(f"\n=== {conf} CONFIDENCE ({len(conf_dups)} pairs) ===")
            for dup in conf_dups[:5]:
                shown += 1
                items = dup['items']
                scores = [score_completeness(it) for it in items]
                primary_idx = 0 if scores[0] >= scores[1] else 1

                print(f"\n{shown}. [{dup['confidence']}] {dup['reason']}")
                for j, (item, score) in enumerate(zip(items, scores)):
                    marker = "KEEP" if j == primary_idx else "MERGE"
                    ewg = item.get('ewg_score') or 'N/A'
                    webflow = "✓" if item.get('webflow_id') else "✗"
                    print(f"   [{marker}] {item['inci_name']}")
                    print(f"         ID: {item['id']}, EWG: {ewg}, Webflow: {webflow}, Score: {score}")

            if len(conf_dups) > 5:
                print(f"\n   ... and {len(conf_dups) - 5} more {conf} confidence duplicates")

    if dry_run:
        print("\n" + "=" * 70)
        print("DRY RUN COMPLETE - No changes made")
        print("=" * 70)
        print(f"\nTo actually merge these duplicates, run:")
        print(f"  python {Path(__file__).name} --merge")
        conn.close()
        return {'merged': 0, 'found': len(duplicates)}

    # Actually merge
    print("\n" + "=" * 70)
    print("MERGING DUPLICATES")
    print("=" * 70)

    merged_count = 0
    deleted_count = 0
    alias_count = 0
    errors = []

    for i, dup in enumerate(duplicates, 1):
        items = dup['items']
        scores = [score_completeness(it) for it in items]
        primary_idx = 0 if scores[0] >= scores[1] else 1
        secondary_idx = 1 - primary_idx

        primary = items[primary_idx]
        secondary = items[secondary_idx]

        print(f"\n[{i}/{len(duplicates)}] Merging: {secondary['inci_name']} -> {primary['inci_name']}")

        try:
            # Merge data
            merged_data = merge_ingredient_data(primary, secondary)
            merged_data['updated_at'] = datetime.now().isoformat()

            # Update primary with merged data
            set_clause = ', '.join(f'{k} = ?' for k in merged_data.keys() if k not in ['id', 'inci_name', 'slug'])
            values = [v for k, v in merged_data.items() if k not in ['id', 'inci_name', 'slug']]
            values.append(primary['id'])

            cursor.execute(f'UPDATE ingredients SET {set_clause} WHERE id = ?', values)

            # Add alias for the secondary name
            secondary_name = secondary['inci_name'].strip()
            if secondary_name:
                cursor.execute('''
                    INSERT OR REPLACE INTO ingredient_aliases (alias, inci_name)
                    VALUES (?, ?)
                ''', (secondary_name, primary['inci_name']))
                alias_count += 1

            # Delete secondary
            cursor.execute('DELETE FROM ingredients WHERE id = ?', (secondary['id'],))
            deleted_count += 1
            merged_count += 1

            print(f"   ✓ Merged and deleted secondary (added alias)")

        except Exception as e:
            errors.append({'dup': dup, 'error': str(e)})
            print(f"   ✗ Error: {e}")

    # Commit changes
    conn.commit()

    # Summary
    print("\n" + "=" * 70)
    print("MERGE COMPLETE")
    print("=" * 70)
    print(f"Duplicate pairs processed: {len(duplicates)}")
    print(f"Successfully merged: {merged_count}")
    print(f"Ingredients deleted: {deleted_count}")
    print(f"Aliases created: {alias_count}")
    print(f"Errors: {len(errors)}")

    if errors:
        print("\nErrors:")
        for err in errors[:5]:
            print(f"  - {err['dup']['items'][0]['inci_name']}: {err['error']}")

    # Final stats
    cursor.execute('SELECT COUNT(*) FROM ingredients')
    new_total = cursor.fetchone()[0]
    print(f"\nIngredients before: {total}")
    print(f"Ingredients after: {new_total}")
    print(f"Reduced by: {total - new_total}")

    conn.close()
    return {'merged': merged_count, 'deleted': deleted_count, 'found': len(duplicates)}


if __name__ == '__main__':
    dry_run = '--merge' not in sys.argv
    safe_only = '--safe-only' in sys.argv

    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        sys.exit(0)

    result = merge_duplicates(dry_run=dry_run, safe_only=safe_only)

    if dry_run:
        print("\nOptions:")
        print("  python find_and_merge_duplicates.py --safe-only   # Show only HIGH/MEDIUM confidence")
        print("  python find_and_merge_duplicates.py --merge       # Merge all duplicates")
        print("  python find_and_merge_duplicates.py --merge --safe-only  # Merge only safe duplicates")
