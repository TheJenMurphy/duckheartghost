"""
INCI Ingredient List Parser

Parses ingredient lists from cosmetic products into individual ingredients.
Handles various formatting styles used by different brands.
"""

import re
from typing import List, Tuple, Optional


class IngredientParser:
    """Parses INCI ingredient lists into individual ingredients."""

    # Common ingredient list prefixes to remove
    PREFIXES = [
        r'^ingredients?\s*[:\-]?\s*',
        r'^full\s+ingredients?\s*[:\-]?\s*',
        r'^active\s+ingredients?\s*[:\-]?\s*',
        r'^inactive\s+ingredients?\s*[:\-]?\s*',
        r'^key\s+ingredients?\s*[:\-]?\s*',
        r'^contains?\s*[:\-]?\s*',
        r'^made\s+with\s*[:\-]?\s*',
    ]

    # Concentration/percentage patterns to clean
    CONCENTRATION_PATTERNS = [
        r'\s*\(\s*\d+\.?\d*\s*%?\s*\)',  # (0.5%) or (5)
        r'\s*\[\s*\d+\.?\d*\s*%?\s*\]',  # [0.5%]
        r'\s+\d+\.?\d*\s*%',              # 0.5%
    ]

    # Common parenthetical additions to handle
    PARENTHETICAL_PATTERNS = [
        r'\s*\((?:and|&)\s*([^)]+)\)',    # (and Vitamin E) -> separate ingredient
        r'\s*\((?:from|derived from)\s+[^)]+\)',  # (from coconut) -> remove
        r'\s*\((?:organic|certified)\s*[^)]*\)',  # (organic) -> remove
        r'\s*\(\s*[ivx]+\s*\)',            # (ii) roman numerals -> remove
    ]

    def __init__(self):
        # Compile regex patterns
        self._prefix_patterns = [re.compile(p, re.IGNORECASE) for p in self.PREFIXES]
        self._concentration_patterns = [re.compile(p) for p in self.CONCENTRATION_PATTERNS]

    def parse(self, ingredient_text: str) -> List[str]:
        """
        Parse an ingredient list string into individual ingredients.

        Args:
            ingredient_text: Raw ingredient list from product page

        Returns:
            List of cleaned, individual ingredient names
        """
        if not ingredient_text:
            return []

        # Clean and normalize text
        text = self._clean_text(ingredient_text)

        # Remove common prefixes
        text = self._remove_prefixes(text)

        # Split into individual ingredients
        raw_ingredients = self._split_ingredients(text)

        # Clean each ingredient
        cleaned = []
        for ing in raw_ingredients:
            clean = self._clean_ingredient(ing)
            if clean and self._is_valid_ingredient(clean):
                cleaned.append(clean)

        return cleaned

    def _clean_text(self, text: str) -> str:
        """Initial text cleanup."""
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove HTML entities
        text = re.sub(r'&[a-z]+;', ' ', text)

        # Normalize separators
        text = text.replace('•', ',')
        text = text.replace('·', ',')
        text = text.replace('|', ',')
        text = text.replace('\n', ', ')

        # Remove asterisks (often used for footnotes)
        text = re.sub(r'\*+', '', text)

        return text.strip()

    def _remove_prefixes(self, text: str) -> str:
        """Remove common ingredient list prefixes."""
        for pattern in self._prefix_patterns:
            text = pattern.sub('', text)
        return text.strip()

    def _split_ingredients(self, text: str) -> List[str]:
        """
        Split ingredient list into individual items.
        Handles comma-separated, period-separated, and nested formats.
        """
        # Handle nested ingredients: "A (and B, C)" -> "A, B, C"
        text = self._flatten_nested(text)

        # Primary split on commas
        parts = text.split(',')

        # Handle period-separated lists (less common)
        if len(parts) < 3:
            # Might be period-separated
            period_parts = re.split(r'\.\s+(?=[A-Z])', text)
            if len(period_parts) > len(parts):
                parts = period_parts

        return [p.strip() for p in parts if p.strip()]

    def _flatten_nested(self, text: str) -> str:
        """
        Flatten nested ingredient formats.
        E.g., "Base (A, B, C)" -> "Base, A, B, C"
        """
        # Match parenthetical lists that look like nested ingredients
        def replace_nested(match):
            content = match.group(1)
            # Check if content looks like ingredient list
            if ',' in content or re.search(r'\b(?:and|&)\b', content):
                # Extract the ingredients
                items = re.split(r'\s*[,&]\s*|\s+and\s+', content)
                return ', ' + ', '.join(items)
            return match.group(0)  # Keep as-is

        text = re.sub(r'\(([^)]+)\)', replace_nested, text)
        return text

    def _clean_ingredient(self, ingredient: str) -> str:
        """Clean individual ingredient name."""
        # Remove concentrations
        for pattern in self._concentration_patterns:
            ingredient = pattern.sub('', ingredient)

        # Remove common parenthetical notes
        for pattern in self.PARENTHETICAL_PATTERNS:
            ingredient = re.sub(pattern, '', ingredient, flags=re.IGNORECASE)

        # Remove remaining parentheses with simple content
        ingredient = re.sub(r'\s*\([^)]{1,20}\)', '', ingredient)

        # Remove leading numbers (sometimes used as markers)
        ingredient = re.sub(r'^\d+\.\s*', '', ingredient)

        # Clean up whitespace
        ingredient = re.sub(r'\s+', ' ', ingredient)
        ingredient = ingredient.strip(' .,;:-')

        # Title case if all caps or all lower
        if ingredient.isupper() or ingredient.islower():
            ingredient = ingredient.title()

        return ingredient

    def _is_valid_ingredient(self, ingredient: str) -> bool:
        """Check if string looks like a valid ingredient name."""
        # Too short
        if len(ingredient) < 2:
            return False

        # Too long (probably description text)
        if len(ingredient) > 100:
            return False

        # Contains sentences (not an ingredient)
        if re.search(r'[.!?]\s+[A-Z]', ingredient):
            return False

        # Common non-ingredient words
        skip_words = [
            'may contain', 'also contains', 'warning', 'caution',
            'directions', 'apply', 'use', 'avoid', 'for best results',
            'this product', 'free of', 'without', 'no ', 'non-',
        ]
        ing_lower = ingredient.lower()
        for word in skip_words:
            if word in ing_lower:
                return False

        return True

    def extract_from_html(self, html: str) -> Tuple[List[str], str]:
        """
        Extract ingredients from HTML, finding the ingredient section.

        Returns:
            Tuple of (list of ingredients, raw ingredient text)
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'html.parser')

        # Try to find ingredient section
        raw_text = self._find_ingredient_section(soup)

        if not raw_text:
            return [], ''

        ingredients = self.parse(raw_text)
        return ingredients, raw_text

    def _find_ingredient_section(self, soup) -> Optional[str]:
        """Find the ingredients section in parsed HTML."""
        # Common selectors for ingredient sections
        selectors = [
            '[data-ingredients]',
            '[id*="ingredient"]',
            '[class*="ingredient"]',
            '[itemprop="ingredients"]',
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(separator=' ', strip=True)
                if len(text) > 30:
                    return text

        # Look for headings followed by ingredient text
        for heading in soup.find_all(['h2', 'h3', 'h4', 'strong', 'b']):
            heading_text = heading.get_text(strip=True).lower()
            if 'ingredient' in heading_text:
                # Get next sibling or parent's text
                next_elem = heading.find_next_sibling()
                if next_elem:
                    text = next_elem.get_text(separator=' ', strip=True)
                    if self._looks_like_ingredients(text):
                        return text

        # Last resort: search all text for ingredient patterns
        all_text = soup.get_text(separator='\n', strip=True)
        lines = all_text.split('\n')

        for i, line in enumerate(lines):
            if re.search(r'^\s*(?:full\s+)?ingredients?\s*[:;]?\s*$', line, re.IGNORECASE):
                # Next non-empty line is likely ingredients
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip() and self._looks_like_ingredients(lines[j]):
                        return lines[j]

        return None

    def _looks_like_ingredients(self, text: str) -> bool:
        """Check if text looks like an ingredient list."""
        # Must have commas (ingredient separator)
        if text.count(',') < 2:
            return False

        # Check for common INCI indicators
        inci_indicators = [
            'aqua', 'water', 'glycerin', 'dimethicone', 'tocopherol',
            'sodium', 'potassium', 'acid', 'extract', 'oil', 'butter',
        ]

        text_lower = text.lower()
        matches = sum(1 for ind in inci_indicators if ind in text_lower)

        return matches >= 2


def parse_ingredient_list(text: str) -> List[str]:
    """
    Convenience function to parse an ingredient list.

    Args:
        text: Raw ingredient list text

    Returns:
        List of cleaned ingredient names
    """
    parser = IngredientParser()
    return parser.parse(text)


# Example ingredient lists for testing
EXAMPLE_LISTS = [
    # Standard comma-separated
    "Water, Glycerin, Butylene Glycol, Dimethicone, Niacinamide, Phenoxyethanol",

    # With concentrations
    "Water, Glycerin (10%), Hyaluronic Acid (0.1%), Retinol (0.5%)",

    # With parenthetical notes
    "Aqua (Water), Glycerin (Vegetable), Tocopherol (Vitamin E)",

    # Nested format
    "Base (Water, Glycerin, Propanediol), Active Complex (Niacinamide, Retinol)",

    # With prefix
    "Ingredients: Water, Glycerin, Butylene Glycol, Dimethicone",

    # May contain line
    "Water, Iron Oxides. May Contain: Titanium Dioxide, Mica.",
]


if __name__ == '__main__':
    import sys

    parser = IngredientParser()

    if len(sys.argv) > 1:
        # Parse provided text
        text = ' '.join(sys.argv[1:])
        ingredients = parser.parse(text)
        print(f"Found {len(ingredients)} ingredients:")
        for i, ing in enumerate(ingredients, 1):
            print(f"  {i}. {ing}")
    else:
        # Test with examples
        print("Testing ingredient parser with example lists:\n")
        for text in EXAMPLE_LISTS:
            print(f"Input: {text[:60]}...")
            ingredients = parser.parse(text)
            print(f"  Parsed: {ingredients}")
            print()
