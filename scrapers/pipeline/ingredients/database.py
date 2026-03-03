"""
SQLite database for ingredient caching and lookup.
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Tuple
from contextlib import contextmanager

from .models import IngredientData


# Default database path
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'data',
    'ingredients.db'
)


class IngredientDatabase:
    """SQLite database for ingredient data with caching and fuzzy search."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure_directory()
        self._init_schema()

    def _ensure_directory(self):
        """Create database directory if it doesn't exist."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main ingredients table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ingredients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inci_name TEXT UNIQUE NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    common_names TEXT,
                    -- EWG data
                    ewg_score INTEGER,
                    ewg_concern_level TEXT,
                    ewg_data_availability TEXT,
                    ewg_url TEXT,
                    ewg_id TEXT,
                    cancer_concern TEXT,
                    developmental_concern TEXT,
                    allergy_concern TEXT,
                    organ_toxicity TEXT,
                    -- CIR data
                    cir_safety TEXT,
                    cir_conditions TEXT,
                    cir_url TEXT,
                    cir_id TEXT,
                    cir_year INTEGER,
                    -- CosIng data
                    cas_number TEXT,
                    ec_number TEXT,
                    cosing_id TEXT,
                    -- PubChem data
                    pubchem_cid INTEGER,
                    molecular_formula TEXT,
                    molecular_weight REAL,
                    -- General info
                    function TEXT,
                    description TEXT,
                    banned_regions TEXT,
                    -- Botanical data
                    plant_family TEXT,
                    plant_part TEXT,
                    origin TEXT,
                    process TEXT,
                    -- Physical properties
                    form TEXT,
                    scent TEXT,
                    -- Uses
                    aromatherapy_uses TEXT,
                    medicinal_uses TEXT,
                    chemistry_nutrients TEXT,
                    -- Classification
                    kind TEXT,
                    -- Persona scores
                    persona_gentle INTEGER,
                    persona_skeptic INTEGER,
                    persona_family INTEGER,
                    persona_antiaging INTEGER,
                    persona_genz INTEGER,
                    persona_inclusive INTEGER,
                    -- Safety
                    safety_concerns TEXT,
                    contraindications TEXT,
                    -- Flags
                    is_clean INTEGER DEFAULT 0,
                    is_controversial INTEGER DEFAULT 0,
                    webflow_id TEXT,
                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ewg_scraped_at TIMESTAMP,
                    cir_scraped_at TIMESTAMP,
                    cosing_scraped_at TIMESTAMP,
                    pubchem_scraped_at TIMESTAMP
                )
            ''')

            # Aliases table for name variations
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ingredient_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias TEXT UNIQUE NOT NULL,
                    inci_name TEXT NOT NULL,
                    FOREIGN KEY (inci_name) REFERENCES ingredients(inci_name)
                )
            ''')

            # Run migrations for existing databases (before creating indexes on new columns)
            self._migrate_schema(cursor)

            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_inci_name ON ingredients(inci_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_slug ON ingredients(slug)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ewg_score ON ingredients(ewg_score)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cir_safety ON ingredients(cir_safety)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alias ON ingredient_aliases(alias)')

            # Create indexes on new columns (may not exist in older databases)
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_cas_number ON ingredients(cas_number)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_kind ON ingredients(kind)')
            except sqlite3.OperationalError:
                pass  # Columns might not exist yet

    def _migrate_schema(self, cursor):
        """Add missing columns to existing database tables."""
        # Get existing columns
        cursor.execute("PRAGMA table_info(ingredients)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # New columns to add (column_name, type, default)
        new_columns = [
            ('cas_number', 'TEXT', None),
            ('ec_number', 'TEXT', None),
            ('cosing_id', 'TEXT', None),
            ('pubchem_cid', 'INTEGER', None),
            ('molecular_formula', 'TEXT', None),
            ('molecular_weight', 'REAL', None),
            ('plant_family', 'TEXT', None),
            ('plant_part', 'TEXT', None),
            ('origin', 'TEXT', None),
            ('process', 'TEXT', None),
            ('form', 'TEXT', None),
            ('scent', 'TEXT', None),
            ('aromatherapy_uses', 'TEXT', None),
            ('medicinal_uses', 'TEXT', None),
            ('chemistry_nutrients', 'TEXT', None),
            ('kind', 'TEXT', None),
            ('persona_gentle', 'INTEGER', None),
            ('persona_skeptic', 'INTEGER', None),
            ('persona_family', 'INTEGER', None),
            ('persona_antiaging', 'INTEGER', None),
            ('persona_genz', 'INTEGER', None),
            ('persona_inclusive', 'INTEGER', None),
            ('safety_concerns', 'TEXT', None),
            ('contraindications', 'TEXT', None),
            ('cosing_scraped_at', 'TIMESTAMP', None),
            ('pubchem_scraped_at', 'TIMESTAMP', None),
        ]

        for col_name, col_type, default in new_columns:
            if col_name not in existing_columns:
                default_clause = f" DEFAULT {default}" if default is not None else ""
                try:
                    cursor.execute(f"ALTER TABLE ingredients ADD COLUMN {col_name} {col_type}{default_clause}")
                except sqlite3.OperationalError:
                    pass  # Column might already exist

    def add_ingredient(self, ingredient: IngredientData) -> int:
        """Add a new ingredient. Returns row ID."""
        return self.upsert(ingredient)

    def update_ingredient(self, inci_name: str, data: dict) -> bool:
        """Update specific fields of an ingredient."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            data['updated_at'] = datetime.now().isoformat()

            set_clause = ', '.join(f'{k} = ?' for k in data.keys())
            values = list(data.values())
            values.append(inci_name)

            cursor.execute(
                f'UPDATE ingredients SET {set_clause} WHERE inci_name = ?',
                values
            )
            return cursor.rowcount > 0

    def upsert(self, ingredient: IngredientData) -> int:
        """Insert or update an ingredient. Returns row ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            data = ingredient.to_dict()
            data['updated_at'] = datetime.now().isoformat()

            # Check if exists by name
            cursor.execute(
                'SELECT id FROM ingredients WHERE LOWER(inci_name) = LOWER(?)',
                (ingredient.inci_name,)
            )
            existing = cursor.fetchone()

            # Also check by slug to avoid collisions
            if not existing:
                cursor.execute(
                    'SELECT id, inci_name FROM ingredients WHERE slug = ?',
                    (ingredient.slug,)
                )
                slug_match = cursor.fetchone()
                if slug_match:
                    # Slug exists with different name - update that record instead
                    existing = slug_match

            if existing:
                # Update
                set_clause = ', '.join(f'{k} = ?' for k in data.keys() if k != 'inci_name' and k != 'slug')
                values = [v for k, v in data.items() if k != 'inci_name' and k != 'slug']
                values.append(existing['id'])

                cursor.execute(
                    f'UPDATE ingredients SET {set_clause} WHERE id = ?',
                    values
                )
                return existing['id']
            else:
                # Insert - ensure unique slug
                base_slug = ingredient.slug
                counter = 1
                while True:
                    cursor.execute('SELECT id FROM ingredients WHERE slug = ?', (data['slug'],))
                    if not cursor.fetchone():
                        break
                    data['slug'] = f'{base_slug}-{counter}'
                    counter += 1

                data['created_at'] = datetime.now().isoformat()
                columns = ', '.join(data.keys())
                placeholders = ', '.join('?' * len(data))

                cursor.execute(
                    f'INSERT INTO ingredients ({columns}) VALUES ({placeholders})',
                    list(data.values())
                )
                return cursor.lastrowid

    def get_by_name(self, name: str) -> Optional[IngredientData]:
        """Get ingredient by exact INCI name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM ingredients WHERE LOWER(inci_name) = LOWER(?)',
                (name,)
            )
            row = cursor.fetchone()
            if row:
                return IngredientData.from_dict(dict(row))
            return None

    def get_by_slug(self, slug: str) -> Optional[IngredientData]:
        """Get ingredient by slug."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ingredients WHERE slug = ?', (slug,))
            row = cursor.fetchone()
            if row:
                return IngredientData.from_dict(dict(row))
            return None

    def search(self, query: str, limit: int = 10) -> List[IngredientData]:
        """Search ingredients by name (fuzzy match)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Search in inci_name and common_names
            search_term = f'%{query}%'
            cursor.execute('''
                SELECT * FROM ingredients
                WHERE LOWER(inci_name) LIKE LOWER(?)
                   OR LOWER(common_names) LIKE LOWER(?)
                ORDER BY
                    CASE
                        WHEN LOWER(inci_name) = LOWER(?) THEN 0
                        WHEN LOWER(inci_name) LIKE LOWER(?) THEN 1
                        ELSE 2
                    END,
                    inci_name
                LIMIT ?
            ''', (search_term, search_term, query, f'{query}%', limit))

            return [IngredientData.from_dict(dict(row)) for row in cursor.fetchall()]

    def lookup(self, name: str) -> Optional[IngredientData]:
        """
        Look up ingredient by name, checking aliases first.
        Returns None if not found.
        """
        # Normalize name
        normalized = self._normalize_name(name)

        # Check exact match
        result = self.get_by_name(normalized)
        if result:
            return result

        # Check aliases
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT inci_name FROM ingredient_aliases WHERE LOWER(alias) = LOWER(?)',
                (normalized,)
            )
            alias_row = cursor.fetchone()
            if alias_row:
                return self.get_by_name(alias_row['inci_name'])

        # Try fuzzy search with high confidence
        results = self.search(normalized, limit=1)
        if results and self._is_close_match(normalized, results[0].inci_name):
            return results[0]

        return None

    def _normalize_name(self, name: str) -> str:
        """Normalize ingredient name for matching."""
        import re
        # Remove parenthetical notes like "(0.3%)" or "(and)"
        name = re.sub(r'\([^)]*\)', '', name)
        # Remove leading/trailing whitespace
        name = name.strip()
        # Normalize whitespace
        name = re.sub(r'\s+', ' ', name)
        return name

    def _is_close_match(self, query: str, candidate: str) -> bool:
        """Check if candidate is a close enough match to query."""
        q_lower = query.lower()
        c_lower = candidate.lower()

        # Exact match
        if q_lower == c_lower:
            return True

        # One contains the other
        if q_lower in c_lower or c_lower in q_lower:
            return True

        # Simple Levenshtein distance for short names
        if len(query) < 20:
            distance = self._levenshtein(q_lower, c_lower)
            max_distance = max(1, len(query) // 5)
            return distance <= max_distance

        return False

    def _levenshtein(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein(s2, s1)

        if len(s2) == 0:
            return len(s1)

        prev_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row

        return prev_row[-1]

    def add_alias(self, alias: str, inci_name: str):
        """Add an alias for an ingredient."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    'INSERT OR REPLACE INTO ingredient_aliases (alias, inci_name) VALUES (?, ?)',
                    (alias.strip(), inci_name)
                )
            except sqlite3.IntegrityError:
                pass  # Alias already exists

    def get_all(self, limit: int = None, offset: int = 0) -> List[IngredientData]:
        """Get all ingredients with optional pagination."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if limit:
                cursor.execute(
                    'SELECT * FROM ingredients ORDER BY inci_name LIMIT ? OFFSET ?',
                    (limit, offset)
                )
            else:
                cursor.execute('SELECT * FROM ingredients ORDER BY inci_name')
            return [IngredientData.from_dict(dict(row)) for row in cursor.fetchall()]

    def get_by_ewg_score(self, min_score: int = None, max_score: int = None) -> List[IngredientData]:
        """Get ingredients filtered by EWG score range."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = 'SELECT * FROM ingredients WHERE ewg_score IS NOT NULL'
            params = []

            if min_score is not None:
                query += ' AND ewg_score >= ?'
                params.append(min_score)
            if max_score is not None:
                query += ' AND ewg_score <= ?'
                params.append(max_score)

            query += ' ORDER BY ewg_score'
            cursor.execute(query, params)
            return [IngredientData.from_dict(dict(row)) for row in cursor.fetchall()]

    def get_clean_ingredients(self) -> List[IngredientData]:
        """Get all ingredients marked as clean."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM ingredients WHERE is_clean = 1 ORDER BY inci_name'
            )
            return [IngredientData.from_dict(dict(row)) for row in cursor.fetchall()]

    def get_concerning_ingredients(self) -> List[IngredientData]:
        """Get ingredients with cancer, developmental, or allergy concerns."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM ingredients
                WHERE cancer_concern IN ('Moderate', 'High')
                   OR developmental_concern IN ('Moderate', 'High')
                   OR allergy_concern IN ('Moderate', 'High')
                   OR ewg_score >= 7
                ORDER BY ewg_score DESC
            ''')
            return [IngredientData.from_dict(dict(row)) for row in cursor.fetchall()]

    def get_without_webflow_id(self, limit: int = 100) -> List[IngredientData]:
        """Get ingredients not yet synced to Webflow."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM ingredients WHERE webflow_id IS NULL LIMIT ?',
                (limit,)
            )
            return [IngredientData.from_dict(dict(row)) for row in cursor.fetchall()]

    def set_webflow_id(self, inci_name: str, webflow_id: str):
        """Update Webflow ID for an ingredient after sync."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE ingredients SET webflow_id = ?, updated_at = ? WHERE inci_name = ?',
                (webflow_id, datetime.now().isoformat(), inci_name)
            )

    def count(self) -> int:
        """Get total ingredient count."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM ingredients')
            return cursor.fetchone()[0]

    def count_with_ewg(self) -> int:
        """Get count of ingredients with EWG data."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM ingredients WHERE ewg_score IS NOT NULL')
            return cursor.fetchone()[0]

    def count_with_cir(self) -> int:
        """Get count of ingredients with CIR data."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM ingredients WHERE cir_safety IS NOT NULL')
            return cursor.fetchone()[0]

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            stats = {}
            cursor.execute('SELECT COUNT(*) FROM ingredients')
            stats['total'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM ingredients WHERE ewg_score IS NOT NULL')
            stats['with_ewg'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM ingredients WHERE cir_safety IS NOT NULL')
            stats['with_cir'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM ingredients WHERE is_clean = 1')
            stats['clean'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM ingredients WHERE ewg_score >= 7')
            stats['high_concern'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM ingredients WHERE webflow_id IS NOT NULL')
            stats['synced_to_webflow'] = cursor.fetchone()[0]

            cursor.execute('SELECT AVG(ewg_score) FROM ingredients WHERE ewg_score IS NOT NULL')
            avg = cursor.fetchone()[0]
            stats['average_ewg_score'] = round(avg, 2) if avg else None

            return stats


# Common ingredient aliases (Water, Glycerin variants, etc.)
COMMON_ALIASES = {
    'Water': ['Aqua', 'Eau', 'Purified Water', 'Deionized Water'],
    'Glycerin': ['Glycerine', 'Glycerol', 'Vegetable Glycerin'],
    'Fragrance': ['Parfum', 'Aroma'],
    'Tocopherol': ['Vitamin E', 'D-Alpha Tocopherol', 'Mixed Tocopherols'],
    'Retinol': ['Vitamin A', 'Retinyl Palmitate', 'Retinyl Acetate'],
    'Ascorbic Acid': ['Vitamin C', 'L-Ascorbic Acid'],
    'Niacinamide': ['Vitamin B3', 'Nicotinamide'],
    'Panthenol': ['Vitamin B5', 'Pro-Vitamin B5', 'Provitamin B5'],
    'Sodium Chloride': ['Salt', 'Sea Salt'],
    'Citric Acid': ['Citrate'],
    'Sodium Hydroxide': ['Lye'],
    'Titanium Dioxide': ['CI 77891'],
    'Iron Oxides': ['CI 77491', 'CI 77492', 'CI 77499'],
}


def seed_common_aliases(db: IngredientDatabase):
    """Seed the database with common ingredient aliases."""
    for inci_name, aliases in COMMON_ALIASES.items():
        for alias in aliases:
            db.add_alias(alias, inci_name)
