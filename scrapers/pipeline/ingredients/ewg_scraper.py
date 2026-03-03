"""
EWG Skin Deep Database Scraper

Scrapes ingredient safety data from https://www.ewg.org/skindeep/
"""

import re
import time
import requests
from typing import Optional, List, Dict
from datetime import datetime
from bs4 import BeautifulSoup

from .models import IngredientData
from .database import IngredientDatabase


# Rate limiting
REQUEST_DELAY = 2.0  # seconds between requests
USER_AGENT = 'iHeartClean-IngredientScraper/1.0 (cosmetic safety research)'

# EWG URL patterns
EWG_BASE_URL = 'https://www.ewg.org/skindeep'
EWG_INGREDIENT_URL = f'{EWG_BASE_URL}/ingredients/'
EWG_SEARCH_URL = f'{EWG_BASE_URL}/search/'


class EWGScraper:
    """Scrapes ingredient data from EWG Skin Deep database."""

    def __init__(self, db: IngredientDatabase = None):
        self.db = db or IngredientDatabase()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self._last_request = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self._last_request = time.time()

    def _get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page with rate limiting."""
        self._rate_limit()
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return BeautifulSoup(resp.text, 'html.parser')
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def search_ingredient(self, name: str) -> List[Dict]:
        """
        Search EWG for an ingredient by name.
        Returns list of search results with ID and name.
        """
        # Use ingredients-specific search for better results
        search_url = f'{EWG_SEARCH_URL}?search={requests.utils.quote(name)}&search_type=ingredients'
        soup = self._get_page(search_url)
        if not soup:
            return []

        results = []
        seen_ids = set()

        # Look for ingredient links in search results
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '/ingredients/' in href:
                # Extract ID and name from URL pattern: /ingredients/ID-NAME/
                match = re.search(r'/ingredients/(\d+)-([^/]+)', href)
                if match:
                    ewg_id = match.group(1)
                    # Skip duplicates
                    if ewg_id in seen_ids:
                        continue
                    seen_ids.add(ewg_id)

                    slug = match.group(2)
                    # Clean up slug to get display name
                    display_name = slug.replace('_', ' ').replace('-', ' ').title()
                    # Use link text if available and meaningful
                    link_text = link.get_text(strip=True)
                    if link_text and len(link_text) > 2 and len(link_text) < 100:
                        display_name = link_text

                    results.append({
                        'ewg_id': ewg_id,
                        'slug': slug,
                        'name': display_name,
                        'url': f'{EWG_BASE_URL}/ingredients/{ewg_id}-{slug}/'
                    })

        return results

    def scrape_ingredient_by_id(self, ewg_id: str, slug: str = '') -> Optional[IngredientData]:
        """
        Scrape ingredient data by EWG ID.
        Returns IngredientData or None if not found.
        """
        if slug:
            url = f'{EWG_INGREDIENT_URL}{ewg_id}-{slug}/'
        else:
            url = f'{EWG_INGREDIENT_URL}{ewg_id}/'

        return self._scrape_ingredient_page(url, ewg_id)

    def scrape_ingredient_by_name(self, name: str) -> Optional[IngredientData]:
        """
        Search for ingredient by name and scrape its data.
        Returns IngredientData or None if not found.
        """
        # First try database
        existing = self.db.get_by_name(name)
        if existing and existing.ewg_score is not None:
            return existing

        # Search EWG
        results = self.search_ingredient(name)
        if not results:
            return None

        # Find best match
        best_match = self._find_best_match(name, results)
        if not best_match:
            return None

        return self.scrape_ingredient_by_id(best_match['ewg_id'], best_match['slug'])

    def _find_best_match(self, query: str, results: List[Dict]) -> Optional[Dict]:
        """Find the best matching result for a query."""
        if not results:
            return None

        query_lower = query.lower().strip()
        query_words = set(query_lower.split())

        # Score each result
        scored = []
        for r in results:
            name_lower = r['name'].lower()
            slug_lower = r['slug'].lower().replace('_', ' ')
            score = 0

            # Exact match - highest priority
            if name_lower == query_lower or slug_lower == query_lower:
                score = 100

            # Starts with query
            elif name_lower.startswith(query_lower) or slug_lower.startswith(query_lower):
                score = 80

            # Query is a word in the name (e.g., "Retinol" in "Retinol Vitamin A")
            elif query_lower in name_lower.split() or query_lower in slug_lower.split():
                score = 70

            # Contains query as substring
            elif query_lower in name_lower or query_lower in slug_lower:
                score = 50

            # Any word overlap
            else:
                name_words = set(name_lower.split())
                overlap = len(query_words & name_words)
                if overlap > 0:
                    score = 30 + (overlap * 10)

            if score > 0:
                scored.append((score, r))

        if scored:
            # Return highest scoring match
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1]

        # Fallback to first result
        return results[0]

    def _scrape_ingredient_page(self, url: str, ewg_id: str = None) -> Optional[IngredientData]:
        """Scrape a single ingredient page."""
        soup = self._get_page(url)
        if not soup:
            return None

        # Extract ingredient name
        name = self._extract_name(soup)
        if not name:
            return None

        # Extract EWG ID from URL if not provided
        if not ewg_id:
            match = re.search(r'/ingredients/(\d+)', url)
            ewg_id = match.group(1) if match else None

        # Create ingredient data
        ingredient = IngredientData(inci_name=name)
        ingredient.ewg_id = ewg_id
        ingredient.ewg_url = url

        # Extract hazard score
        ingredient.ewg_score = self._extract_score(soup)
        ingredient.ewg_concern_level = self._score_to_concern_level(ingredient.ewg_score)

        # Extract data availability
        ingredient.ewg_data_availability = self._extract_data_availability(soup)

        # Extract health concerns
        concerns = self._extract_concerns(soup)
        ingredient.cancer_concern = concerns.get('cancer')
        ingredient.developmental_concern = concerns.get('developmental')
        ingredient.allergy_concern = concerns.get('allergy')
        ingredient.organ_toxicity = concerns.get('organ_toxicity')

        # Extract function/description
        ingredient.function = self._extract_function(soup)
        ingredient.description = self._extract_description(soup)

        # Extract common names/synonyms
        ingredient.common_names = self._extract_synonyms(soup)

        # Set timestamp
        ingredient.ewg_scraped_at = datetime.now()

        # Compute derived flags
        ingredient._compute_flags()

        return ingredient

    def _extract_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract ingredient name from page."""
        # Method 1: Look for h2 with class "product-name" (EWG's current structure)
        product_name = soup.find('h2', class_='product-name')
        if product_name:
            name = product_name.get_text(strip=True)
            if name and len(name) > 1:
                return name

        # Method 2: Try title tag - extract ingredient name
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Pattern: "EWG Skin Deep® | What is INGREDIENT_NAME"
            match = re.search(r'What is\s+(.+?)(?:\s*$|\s*-|\s*\|)', title, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Method 3: Try og:title meta tag
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title.get('content', '')
            match = re.search(r'What is\s+(.+?)(?:\s*$|\s*-|\s*\|)', title, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Method 4: Fallback to h1
        h1 = soup.find('h1')
        if h1:
            name = h1.get_text(strip=True)
            name = re.sub(r'^What is\s+', '', name, flags=re.IGNORECASE)
            name = re.sub(r'\?$', '', name)
            if name:
                return name.strip()

        return None

    def _extract_score(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract EWG hazard score (1-10)."""
        # Method 1: Look for squircle image with score in URL
        # Pattern: /skindeep/squircle/show.svg?score=4&score_min=1
        squircle = soup.find('img', class_='squircle')
        if squircle:
            src = squircle.get('src', '')
            match = re.search(r'score=(\d+)', src)
            if match:
                try:
                    score = int(match.group(1))
                    if 1 <= score <= 10:
                        return score
                except ValueError:
                    pass

        # Method 2: Look for any img with score in URL
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if 'score=' in src:
                match = re.search(r'score=(\d+)', src)
                if match:
                    try:
                        score = int(match.group(1))
                        if 1 <= score <= 10:
                            return score
                    except ValueError:
                        pass

        # Method 3: Look for score attribute in any element
        score_elem = soup.find(attrs={'score': True})
        if score_elem:
            try:
                return int(score_elem['score'])
            except (ValueError, TypeError):
                pass

        # Method 4: Look for score in class names
        for elem in soup.find_all(class_=re.compile(r'score-?\d+')):
            match = re.search(r'score-?(\d+)', ' '.join(elem.get('class', [])))
            if match:
                try:
                    score = int(match.group(1))
                    if 1 <= score <= 10:
                        return score
                except ValueError:
                    pass

        # Method 5: Look for score in product-score div text
        product_score = soup.find('div', class_='product-score')
        if product_score:
            text = product_score.get_text()
            match = re.search(r'(\d+)', text)
            if match:
                try:
                    score = int(match.group(1))
                    if 1 <= score <= 10:
                        return score
                except ValueError:
                    pass

        return None

    def _score_to_concern_level(self, score: Optional[int]) -> Optional[str]:
        """Convert numeric score to concern level text."""
        if score is None:
            return None
        if score <= 2:
            return "Low Hazard"
        elif score <= 6:
            return "Moderate Hazard"
        else:
            return "High Hazard"

    def _extract_data_availability(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract data availability rating."""
        # Method 1: Look for "data-level" element (EWG's current structure)
        # Pattern: <p class="data-level">Data: Good</p>
        data_level = soup.find('p', class_='data-level')
        if data_level:
            text = data_level.get_text(strip=True)
            # Extract level from "Data: Good" pattern
            match = re.search(r'Data:\s*(\w+)', text, re.IGNORECASE)
            if match:
                level = match.group(1).capitalize()
                # Normalize to standard values
                if level in ('Good', 'Robust'):
                    return 'Good'
                elif level in ('Fair', 'Moderate'):
                    return 'Fair'
                elif level in ('Limited', 'Poor'):
                    return 'Limited'
                elif level in ('None', 'No'):
                    return 'None'
                return level

        # Method 2: Search full page text for patterns
        text = soup.get_text()
        patterns = [
            (r'Data:\s*Good', 'Good'),
            (r'Data:\s*Fair', 'Fair'),
            (r'Data:\s*Limited', 'Limited'),
            (r'Data:\s*None', 'None'),
            (r'robust\s+(?:data\s+)?availability', 'Good'),
            (r'fair\s+(?:data\s+)?availability', 'Fair'),
            (r'limited\s+(?:data\s+)?availability', 'Limited'),
            (r'no\s+data', 'None'),
        ]

        for pattern, level in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return level

        return None

    def _extract_concerns(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        """Extract health concern levels from structured HTML."""
        concerns = {
            'cancer': None,
            'developmental': None,
            'allergy': None,
            'organ_toxicity': None,
        }

        # Method 1: Parse structured concern list (EWG's current format)
        # Structure: <li class="concern">
        #              <div class="level"><div class="concern-low"></div>LOW</div>
        #              <div class="concern-text">Cancer</div>
        #            </li>
        concern_items = soup.find_all('li', class_='concern')

        for item in concern_items:
            # Get concern type
            concern_text_elem = item.find('div', class_='concern-text')
            if not concern_text_elem:
                continue
            concern_type = concern_text_elem.get_text(strip=True).lower()

            # Get level from class or text
            level_elem = item.find('div', class_='level')
            level = None

            if level_elem:
                # Check for concern-level classes
                level_div = level_elem.find('div', class_=re.compile(r'concern-'))
                if level_div:
                    classes = level_div.get('class', [])
                    for cls in classes:
                        if 'concern-high' in cls:
                            level = 'High'
                            break
                        elif 'concern-moderate' in cls or 'concern-med' in cls:
                            level = 'Moderate'
                            break
                        elif 'concern-low' in cls:
                            level = 'Low'
                            break

                # Fallback to text content
                if not level:
                    level_text = level_elem.get_text(strip=True).upper()
                    if 'HIGH' in level_text:
                        level = 'High'
                    elif 'MODERATE' in level_text or 'MED' in level_text:
                        level = 'Moderate'
                    elif 'LOW' in level_text:
                        level = 'Low'

            # Map to our concern types
            if level:
                if 'cancer' in concern_type:
                    concerns['cancer'] = level
                elif 'allerg' in concern_type or 'immunotox' in concern_type:
                    concerns['allergy'] = level
                elif 'developmental' in concern_type or 'reproductive' in concern_type:
                    concerns['developmental'] = level
                elif 'organ' in concern_type:
                    concerns['organ_toxicity'] = level

        # Method 2: Fallback to text search if structured parsing found nothing
        if not any(concerns.values()):
            text = soup.get_text()

            # Cancer concern
            if re.search(r'(?:cancer|carcinogen).*high', text, re.IGNORECASE):
                concerns['cancer'] = 'High'
            elif re.search(r'(?:cancer|carcinogen).*moderate', text, re.IGNORECASE):
                concerns['cancer'] = 'Moderate'
            elif re.search(r'(?:cancer|carcinogen).*low', text, re.IGNORECASE):
                concerns['cancer'] = 'Low'

            # Allergy concern
            if re.search(r'allerg.*high', text, re.IGNORECASE):
                concerns['allergy'] = 'High'
            elif re.search(r'allerg.*moderate', text, re.IGNORECASE):
                concerns['allergy'] = 'Moderate'
            elif re.search(r'allerg.*low', text, re.IGNORECASE):
                concerns['allergy'] = 'Low'

            # Developmental concern
            if re.search(r'developmental.*high', text, re.IGNORECASE):
                concerns['developmental'] = 'High'
            elif re.search(r'developmental.*moderate', text, re.IGNORECASE):
                concerns['developmental'] = 'Moderate'
            elif re.search(r'developmental.*low', text, re.IGNORECASE):
                concerns['developmental'] = 'Low'

        return concerns

    def _extract_function(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract ingredient function/use."""
        text = soup.get_text()

        # Common function patterns
        functions = [
            'Surfactant', 'Emollient', 'Preservative', 'Fragrance', 'Colorant',
            'Solvent', 'Emulsifier', 'Humectant', 'Conditioning Agent',
            'UV Absorber', 'Antioxidant', 'pH Adjuster', 'Chelating Agent',
            'Thickener', 'Film Former', 'Opacifying Agent', 'Skin Protectant',
        ]

        for func in functions:
            if re.search(rf'\b{func}\b', text, re.IGNORECASE):
                return func

        # Look for "used as" pattern
        match = re.search(r'used\s+(?:as\s+)?(?:a\s+)?([^.]{5,50})', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract ingredient description."""
        # Find first substantial paragraph
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) > 50 and not text.startswith('EWG'):
                # Clean up and truncate
                text = re.sub(r'\s+', ' ', text)
                return text[:500] if len(text) > 500 else text

        return None

    def _extract_synonyms(self, soup: BeautifulSoup) -> List[str]:
        """Extract ingredient synonyms/alternate names."""
        synonyms = []
        text = soup.get_text()

        # Look for "also known as" or "synonyms" section
        match = re.search(
            r'(?:also\s+known\s+as|synonyms?|other\s+names?)[:\s]+([^.]+)',
            text, re.IGNORECASE
        )
        if match:
            names = match.group(1)
            # Split by commas or semicolons
            for name in re.split(r'[,;]', names):
                name = name.strip()
                if name and len(name) < 50:
                    synonyms.append(name)

        return synonyms[:10]  # Limit to 10

    def scrape_and_save(self, name: str) -> Optional[IngredientData]:
        """
        Scrape ingredient by name and save to database.
        Returns the ingredient data or None if not found.
        """
        ingredient = self.scrape_ingredient_by_name(name)
        if ingredient:
            self.db.upsert(ingredient)
            # Add synonyms as aliases
            for syn in ingredient.common_names:
                self.db.add_alias(syn, ingredient.inci_name)
        return ingredient

    def batch_scrape(
        self,
        names: List[str],
        progress_callback=None
    ) -> Dict[str, IngredientData]:
        """
        Scrape multiple ingredients.
        Returns dict mapping names to ingredient data.
        """
        results = {}
        total = len(names)

        for i, name in enumerate(names):
            if progress_callback:
                progress_callback(i + 1, total, name)

            ingredient = self.scrape_and_save(name)
            if ingredient:
                results[name] = ingredient
            else:
                print(f"  Not found: {name}")

        return results


def scrape_common_ingredients(db: IngredientDatabase = None) -> int:
    """
    Scrape a list of common cosmetic ingredients.
    Returns count of ingredients scraped.
    """
    COMMON_INGREDIENTS = [
        'Water', 'Glycerin', 'Butylene Glycol', 'Propanediol', 'Dimethicone',
        'Phenoxyethanol', 'Sodium Hyaluronate', 'Niacinamide', 'Tocopherol',
        'Retinol', 'Ascorbic Acid', 'Salicylic Acid', 'Hyaluronic Acid',
        'Cetearyl Alcohol', 'Stearic Acid', 'Palmitic Acid', 'Cetyl Alcohol',
        'Shea Butter', 'Jojoba Oil', 'Coconut Oil', 'Argan Oil', 'Squalane',
        'Titanium Dioxide', 'Zinc Oxide', 'Iron Oxides', 'Mica',
        'Fragrance', 'Parfum', 'Limonene', 'Linalool', 'Citral',
        'Sodium Lauryl Sulfate', 'Sodium Laureth Sulfate', 'Cocamidopropyl Betaine',
        'Panthenol', 'Allantoin', 'Aloe Barbadensis', 'Chamomilla Recutita',
        'Caffeine', 'Peptides', 'Ceramides', 'Cholesterol',
        'Citric Acid', 'Lactic Acid', 'Glycolic Acid', 'Malic Acid',
        'Ethylhexylglycerin', 'Caprylyl Glycol', 'Hexylene Glycol',
        'PEG-100 Stearate', 'Polysorbate 20', 'Polysorbate 80',
        'Methylparaben', 'Propylparaben', 'Butylparaben',
        'Benzyl Alcohol', 'Potassium Sorbate', 'Sodium Benzoate',
    ]

    scraper = EWGScraper(db)

    def progress(current, total, name):
        print(f"[{current}/{total}] Scraping: {name}")

    results = scraper.batch_scrape(COMMON_INGREDIENTS, progress_callback=progress)
    return len(results)


if __name__ == '__main__':
    import sys

    db = IngredientDatabase()

    if len(sys.argv) > 1:
        # Scrape specific ingredient
        name = ' '.join(sys.argv[1:])
        print(f"Scraping: {name}")
        scraper = EWGScraper(db)
        ingredient = scraper.scrape_and_save(name)
        if ingredient:
            print(f"  Name: {ingredient.inci_name}")
            print(f"  EWG Score: {ingredient.ewg_score}")
            print(f"  Concern Level: {ingredient.ewg_concern_level}")
            print(f"  Cancer Concern: {ingredient.cancer_concern}")
            print(f"  CIR Safety: {ingredient.cir_safety}")
        else:
            print("  Not found")
    else:
        # Scrape common ingredients
        print("Scraping common cosmetic ingredients...")
        count = scrape_common_ingredients(db)
        print(f"\nScraped {count} ingredients")
        print(f"Database stats: {db.get_stats()}")
