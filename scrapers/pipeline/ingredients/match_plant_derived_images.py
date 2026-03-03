#!/usr/bin/env python3
"""
Match plant-derived synthetic ingredients to their source plant images.

For plant-derived synthetic ingredients:
- Hero image: PubChem molecular structure (or rainbow question mark if unavailable)
- Additional images: Images of the plants/sources it's derived from

Example:
  "Sodium Cocoyl/Palmoyl/Sunfloweroyl Glutamate"
  → Hero: molecular structure
  → Additional: salt, coconut, palm, sunflower images

Usage:
  python match_plant_derived_images.py [--dry-run] [--limit=N]
"""

import os
import re
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from difflib import SequenceMatcher
import requests
from urllib.parse import quote

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DB_PATH = DATA_DIR / "ingredients.db"

# Image folders
LOCAL_MASTER = Path.home() / "Downloads" / "ingredient_images_master"
GDRIVE_MASTER = Path.home() / "Library" / "CloudStorage" / "GoogleDrive-hello@iheartclean.beauty" / "My Drive" / "Ingredient Images" / "master"

# Placeholder image URL
PLACEHOLDER_URL = "https://cdn.prod.website-files.com/6759f0a54f1395fcb6c5b78e/69740e012465c0c53004660b_9s-question-mark.png"

# PubChem API
PUBCHEM_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
HEADERS = {'User-Agent': 'iHeartClean-Bot/1.0 (ingredient research)'}


# =============================================================================
# CHEMICAL PREFIX/SUFFIX TO PLANT SOURCE MAPPINGS
# =============================================================================

# Maps chemical prefixes/terms to their plant sources
CHEMICAL_TO_PLANT = {
    # Coconut derivatives
    'coco': ['Coconut', 'Cocos Nucifera'],
    'cocoyl': ['Coconut', 'Cocos Nucifera'],
    'cocamide': ['Coconut', 'Cocos Nucifera'],
    'cocamido': ['Coconut', 'Cocos Nucifera'],
    'cocolate': ['Coconut', 'Cocos Nucifera'],
    'coceth': ['Coconut', 'Cocos Nucifera'],
    'cocoate': ['Coconut', 'Cocos Nucifera'],
    'cocobetaine': ['Coconut', 'Cocos Nucifera'],

    # Palm derivatives
    'palm': ['Palm', 'Palm Oil', 'Elaeis Guineensis'],
    'palmoyl': ['Palm', 'Palm Oil', 'Elaeis Guineensis'],
    'palmitate': ['Palm', 'Palm Oil', 'Elaeis Guineensis'],
    'palmitoyl': ['Palm', 'Palm Oil', 'Elaeis Guineensis'],
    'palmeth': ['Palm', 'Palm Oil', 'Elaeis Guineensis'],
    'palmamide': ['Palm', 'Palm Oil', 'Elaeis Guineensis'],
    'palmkernel': ['Palm', 'Palm Kernel', 'Elaeis Guineensis'],

    # Sunflower derivatives
    'sunflower': ['Sunflower', 'Helianthus Annuus'],
    'sunfloweroyl': ['Sunflower', 'Helianthus Annuus'],
    'sunflowerseed': ['Sunflower', 'Sunflower Seed', 'Helianthus Annuus'],

    # Olive derivatives
    'olive': ['Olive', 'Olea Europaea', 'Olive Oil'],
    'olivoyl': ['Olive', 'Olea Europaea'],
    'olivate': ['Olive', 'Olea Europaea'],
    'oleate': ['Olive', 'Olea Europaea'],  # Can also be general oleic acid
    'oleoyl': ['Olive', 'Olea Europaea'],

    # Soy derivatives
    'soy': ['Soybean', 'Soy', 'Glycine Soja', 'Glycine Max'],
    'soya': ['Soybean', 'Soy', 'Glycine Soja'],

    # Corn/Maize derivatives
    'corn': ['Corn', 'Maize', 'Zea Mays'],
    'maize': ['Corn', 'Maize', 'Zea Mays'],
    'zea': ['Corn', 'Maize', 'Zea Mays'],

    # Wheat derivatives
    'wheat': ['Wheat', 'Triticum Vulgare', 'Triticum Aestivum'],
    'triticum': ['Wheat', 'Triticum Vulgare'],

    # Rice derivatives
    'rice': ['Rice', 'Oryza Sativa'],
    'oryza': ['Rice', 'Oryza Sativa'],

    # Oat derivatives (use word boundary matching - handled in extract function)
    'avena': ['Oat', 'Avena Sativa'],
    # 'oat' removed - too many false positives (cocoate, etc.)

    # Almond derivatives
    'almond': ['Almond', 'Prunus Dulcis', 'Prunus Amygdalus'],
    'amygdalus': ['Almond', 'Prunus Dulcis'],
    'prunus': ['Almond', 'Prunus'],  # Could be various stone fruits

    # Macadamia derivatives
    'macadamia': ['Macadamia', 'Macadamia Ternifolia', 'Macadamia Nut'],
    'macadamiaseed': ['Macadamia', 'Macadamia Seed', 'Macadamia Nut'],

    # Shea derivatives
    'shea': ['Shea', 'Shea Butter', 'Butyrospermum Parkii'],
    'butyrospermum': ['Shea', 'Shea Butter', 'Butyrospermum Parkii'],

    # Jojoba derivatives
    'jojoba': ['Jojoba', 'Simmondsia Chinensis'],
    'simmondsia': ['Jojoba', 'Simmondsia Chinensis'],

    # Castor derivatives
    'castor': ['Castor', 'Ricinus Communis', 'Castor Oil'],
    'ricin': ['Castor', 'Ricinus Communis'],
    'ricinole': ['Castor', 'Ricinus Communis'],

    # Safflower derivatives
    'safflower': ['Safflower', 'Carthamus Tinctorius'],
    'carthamus': ['Safflower', 'Carthamus Tinctorius'],

    # Rapeseed/Canola derivatives
    'rapeseed': ['Rapeseed', 'Canola', 'Brassica Napus'],
    'canola': ['Rapeseed', 'Canola', 'Brassica Napus'],
    'brassica': ['Rapeseed', 'Canola', 'Brassica'],

    # Cottonseed derivatives
    'cotton': ['Cotton', 'Gossypium', 'Cottonseed'],
    'gossypium': ['Cotton', 'Gossypium'],

    # Avocado derivatives
    'avocado': ['Avocado', 'Persea Gratissima', 'Persea Americana'],
    'persea': ['Avocado', 'Persea Gratissima'],

    # Argan derivatives
    'argan': ['Argan', 'Argania Spinosa'],
    'argania': ['Argan', 'Argania Spinosa'],

    # Sesame derivatives
    'sesame': ['Sesame', 'Sesamum Indicum'],
    'sesamum': ['Sesame', 'Sesamum Indicum'],

    # Grape derivatives
    'grape': ['Grape', 'Vitis Vinifera', 'Grapeseed'],
    'vitis': ['Grape', 'Vitis Vinifera'],

    # Lemon/Citrus derivatives
    'lemon': ['Lemon', 'Citrus Limon'],
    'citrus': ['Citrus', 'Lemon', 'Orange'],
    'limon': ['Lemon', 'Citrus Limon'],

    # Orange derivatives
    'orange': ['Orange', 'Citrus Aurantium', 'Citrus Sinensis'],
    'aurantium': ['Orange', 'Citrus Aurantium'],

    # Apple derivatives
    'apple': ['Apple', 'Pyrus Malus', 'Malus Domestica'],
    'malus': ['Apple', 'Malus Domestica'],
    'malic': ['Apple', 'Malic Acid'],  # Malic acid from apples

    # Rose derivatives
    'rose': ['Rose', 'Rosa'],
    'rosa': ['Rose', 'Rosa'],

    # Lavender derivatives
    'lavender': ['Lavender', 'Lavandula'],
    'lavandula': ['Lavender', 'Lavandula'],

    # Tea tree derivatives
    'teatree': ['Tea Tree', 'Melaleuca Alternifolia'],
    'melaleuca': ['Tea Tree', 'Melaleuca'],

    # Green tea/Camellia derivatives
    'greentea': ['Green Tea', 'Camellia Sinensis'],
    'camellia': ['Camellia', 'Green Tea', 'Camellia Sinensis'],

    # Cocoa derivatives
    'cocoa': ['Cocoa', 'Theobroma Cacao', 'Cocoa Butter'],
    'cacao': ['Cocoa', 'Theobroma Cacao'],
    'theobroma': ['Cocoa', 'Theobroma Cacao'],

    # Sugar derivatives
    'sugar': ['Sugar', 'Sugarcane', 'Saccharum'],
    'sucrose': ['Sugar', 'Sugarcane'],
    'saccharum': ['Sugar', 'Sugarcane'],
    'glucose': ['Sugar', 'Corn', 'Glucose'],
    'fructose': ['Sugar', 'Fruit Sugar'],

    # Honey derivatives
    'honey': ['Honey', 'Mel'],
    'mel': ['Honey'],

    # Beeswax derivatives
    'beeswax': ['Beeswax', 'Cera Alba'],
    'cera': ['Beeswax', 'Cera Alba'],

    # Lanolin derivatives
    'lanolin': ['Lanolin', 'Wool'],
    'laneth': ['Lanolin'],
    'lanol': ['Lanolin'],

    # Stearic/Fatty acid sources (often from multiple plants)
    'stear': ['Stearic Acid', 'Coconut', 'Palm'],  # Stearic acid from various fats
    'laur': ['Lauric Acid', 'Coconut', 'Palm Kernel'],  # Lauric acid
    'myrist': ['Myristic Acid', 'Coconut', 'Palm Kernel'],  # Myristic acid
    'capry': ['Caprylic Acid', 'Coconut', 'Palm Kernel'],  # Caprylic acid
    'capr': ['Capric Acid', 'Coconut', 'Palm Kernel'],  # Capric acid
    'cetyl': ['Cetyl Alcohol', 'Coconut', 'Palm'],
    'cetear': ['Cetearyl Alcohol', 'Coconut', 'Palm'],
    'beheni': ['Behenic Acid', 'Rapeseed', 'Canola'],
    'oleyl': ['Oleic Acid', 'Olive', 'Various Oils'],
    'linole': ['Linoleic Acid', 'Sunflower', 'Safflower'],

    # Sodium/Potassium (mineral salts)
    'sodium': ['Salt', 'Sodium Chloride'],
    'potassium': ['Potassium'],

    # Glycerin derivatives (usually from fats)
    'glyceryl': ['Glycerin', 'Vegetable Glycerin'],
    'glycerin': ['Glycerin', 'Vegetable Glycerin'],
    'glycol': ['Glycol'],

    # Glucoside derivatives (sugar + fatty alcohol from plants)
    'glucoside': ['Glucose', 'Sugar', 'Corn'],
    'decyl': ['Coconut', 'Palm Kernel'],  # Decyl from C10 fatty acids
    'lauryl': ['Coconut', 'Lauric Acid'],  # C12 fatty acids
    'capryl': ['Coconut', 'Caprylic Acid'],  # C8 fatty acids
    'octyl': ['Coconut', 'Caprylic Acid'],  # C8

    # Amino acid derivatives
    'glutamate': ['Glutamic Acid'],
    'glycine': ['Glycine', 'Amino Acid'],
    'alanine': ['Alanine', 'Amino Acid'],
    'arginine': ['Arginine', 'Amino Acid'],
    'lysine': ['Lysine', 'Amino Acid'],
    'proline': ['Proline', 'Amino Acid'],

    # Algae/Seaweed derivatives
    'algae': ['Algae', 'Seaweed'],
    'seaweed': ['Seaweed', 'Algae'],
    'kelp': ['Kelp', 'Seaweed'],
    'carrageenan': ['Carrageenan', 'Seaweed', 'Irish Moss'],
    'agar': ['Agar', 'Seaweed'],
    'algin': ['Alginate', 'Seaweed', 'Kelp'],

    # Herb derivatives
    'chamomile': ['Chamomile', 'Anthemis Nobilis', 'Matricaria'],
    'eucalyptus': ['Eucalyptus'],
    'peppermint': ['Peppermint', 'Mentha Piperita'],
    'spearmint': ['Spearmint', 'Mentha Spicata'],
    'rosemary': ['Rosemary', 'Rosmarinus Officinalis'],
    'thyme': ['Thyme', 'Thymus Vulgaris'],
    'sage': ['Sage', 'Salvia'],
    'basil': ['Basil', 'Ocimum Basilicum'],
    'oregano': ['Oregano', 'Origanum Vulgare'],

    # Nut derivatives
    'hazelnut': ['Hazelnut', 'Corylus Avellana'],
    'walnut': ['Walnut', 'Juglans Regia'],
    'pecan': ['Pecan'],
    'brazil': ['Brazil Nut', 'Bertholletia Excelsa'],
    'pistachio': ['Pistachio', 'Pistacia Vera'],
    'cashew': ['Cashew', 'Anacardium Occidentale'],

    # Fruit derivatives
    'berry': ['Berry'],
    'strawberry': ['Strawberry', 'Fragaria'],
    'blueberry': ['Blueberry', 'Vaccinium'],
    'raspberry': ['Raspberry', 'Rubus'],
    'cranberry': ['Cranberry', 'Vaccinium Macrocarpon'],
    'acai': ['Acai', 'Euterpe Oleracea'],
    'goji': ['Goji', 'Lycium Barbarum'],
    'pomegranate': ['Pomegranate', 'Punica Granatum'],
    'mango': ['Mango', 'Mangifera Indica'],
    'papaya': ['Papaya', 'Carica Papaya'],
    'pineapple': ['Pineapple', 'Ananas Comosus'],
    'banana': ['Banana', 'Musa'],
    'kiwi': ['Kiwi', 'Actinidia Chinensis'],
    'peach': ['Peach', 'Prunus Persica'],
    'apricot': ['Apricot', 'Prunus Armeniaca'],
    'plum': ['Plum', 'Prunus Domestica'],
    'cherry': ['Cherry', 'Prunus Cerasus'],
    'fig': ['Fig', 'Ficus Carica'],
    'date': ['Date', 'Phoenix Dactylifera'],

    # Vegetable derivatives
    'carrot': ['Carrot', 'Daucus Carota'],
    'tomato': ['Tomato', 'Solanum Lycopersicum'],
    'cucumber': ['Cucumber', 'Cucumis Sativus'],
    'spinach': ['Spinach', 'Spinacia Oleracea'],
    'broccoli': ['Broccoli', 'Brassica Oleracea'],
    'cabbage': ['Cabbage', 'Brassica Oleracea'],
    'beet': ['Beet', 'Beta Vulgaris'],
    'potato': ['Potato', 'Solanum Tuberosum'],

    # Tree derivatives
    'bamboo': ['Bamboo'],
    'birch': ['Birch', 'Betula'],
    'willow': ['Willow', 'Salix'],
    'oak': ['Oak', 'Quercus'],
    'pine': ['Pine', 'Pinus'],
    'cedar': ['Cedar', 'Cedrus'],
    'sandalwood': ['Sandalwood', 'Santalum Album'],
    'frankincense': ['Frankincense', 'Boswellia'],
    'myrrh': ['Myrrh', 'Commiphora'],

    # Other botanical sources
    'aloe': ['Aloe', 'Aloe Vera', 'Aloe Barbadensis'],
    'vanilla': ['Vanilla', 'Vanilla Planifolia'],
    'ginger': ['Ginger', 'Zingiber Officinale'],
    'turmeric': ['Turmeric', 'Curcuma Longa'],
    'cinnamon': ['Cinnamon', 'Cinnamomum'],
    'clove': ['Clove', 'Eugenia Caryophyllus'],
    'cardamom': ['Cardamom', 'Elettaria Cardamomum'],
    'jasmine': ['Jasmine', 'Jasminum'],
    'ylang': ['Ylang Ylang', 'Cananga Odorata'],
    'neroli': ['Neroli', 'Citrus Aurantium'],
    'bergamot': ['Bergamot', 'Citrus Bergamia'],
    'geranium': ['Geranium', 'Pelargonium'],
    'patchouli': ['Patchouli', 'Pogostemon Cablin'],
    'vetiver': ['Vetiver', 'Vetiveria Zizanioides'],

    # Specific compound prefixes
    'hydrolyzed': [],  # Modifier, not a source
    'hydrogenated': [],  # Modifier
    'peg': [],  # Polyethylene glycol
    'ppg': [],  # Polypropylene glycol
}


# =============================================================================
# SOURCE PRIORITY RANKING
# =============================================================================

# Priority tiers (lower number = higher priority)
# Tier 1: Primary plants - most visually interesting
# Tier 2: Seeds, nuts, tree sources
# Tier 3: Fruits and vegetables
# Tier 4: Herbs, flowers, specialty plants
# Tier 5: Derived compounds (acids, alcohols)
# Tier 6: Minerals and salts (least visually interesting)

SOURCE_PRIORITY = {
    # Tier 1: Primary oil plants (most common, visually distinctive)
    'Coconut': 1, 'Cocos Nucifera': 1,
    'Palm': 1, 'Palm Oil': 1, 'Elaeis Guineensis': 1,
    'Olive': 1, 'Olea Europaea': 1, 'Olive Oil': 1,
    'Sunflower': 1, 'Helianthus Annuus': 1,
    'Soybean': 1, 'Soy': 1, 'Glycine Soja': 1, 'Glycine Max': 1,
    'Corn': 1, 'Maize': 1, 'Zea Mays': 1,
    'Rapeseed': 1, 'Canola': 1, 'Brassica Napus': 1,
    'Safflower': 1, 'Carthamus Tinctorius': 1,
    'Cotton': 1, 'Gossypium': 1, 'Cottonseed': 1,
    'Rice': 1, 'Oryza Sativa': 1,

    # Tier 2: Seeds, nuts, specialty oils
    'Macadamia': 2, 'Macadamia Ternifolia': 2, 'Macadamia Nut': 2, 'Macadamia Seed': 2,
    'Argan': 2, 'Argania Spinosa': 2,
    'Jojoba': 2, 'Simmondsia Chinensis': 2,
    'Shea': 2, 'Shea Butter': 2, 'Butyrospermum Parkii': 2,
    'Castor': 2, 'Ricinus Communis': 2, 'Castor Oil': 2,
    'Almond': 2, 'Prunus Dulcis': 2, 'Prunus Amygdalus': 2,
    'Sesame': 2, 'Sesamum Indicum': 2,
    'Avocado': 2, 'Persea Gratissima': 2, 'Persea Americana': 2,
    'Grape': 2, 'Vitis Vinifera': 2, 'Grapeseed': 2,
    'Wheat': 2, 'Triticum Vulgare': 2, 'Triticum Aestivum': 2,
    'Oat': 2, 'Avena Sativa': 2,
    'Cocoa': 2, 'Theobroma Cacao': 2, 'Cocoa Butter': 2,
    'Hazelnut': 2, 'Corylus Avellana': 2,
    'Walnut': 2, 'Juglans Regia': 2,
    'Brazil Nut': 2, 'Bertholletia Excelsa': 2,
    'Pistachio': 2, 'Pistacia Vera': 2,
    'Cashew': 2, 'Anacardium Occidentale': 2,
    'Palm Kernel': 2,

    # Tier 3: Fruits and vegetables
    'Lemon': 3, 'Citrus Limon': 3,
    'Orange': 3, 'Citrus Aurantium': 3, 'Citrus Sinensis': 3,
    'Citrus': 3,
    'Apple': 3, 'Pyrus Malus': 3, 'Malus Domestica': 3,
    'Pomegranate': 3, 'Punica Granatum': 3,
    'Mango': 3, 'Mangifera Indica': 3,
    'Papaya': 3, 'Carica Papaya': 3,
    'Pineapple': 3, 'Ananas Comosus': 3,
    'Banana': 3, 'Musa': 3,
    'Kiwi': 3, 'Actinidia Chinensis': 3,
    'Peach': 3, 'Prunus Persica': 3,
    'Apricot': 3, 'Prunus Armeniaca': 3,
    'Cucumber': 3, 'Cucumis Sativus': 3,
    'Tomato': 3, 'Solanum Lycopersicum': 3,
    'Carrot': 3, 'Daucus Carota': 3,
    'Beet': 3, 'Beta Vulgaris': 3,
    'Sugar': 3, 'Sugarcane': 3, 'Saccharum': 3,
    'Berry': 3,
    'Strawberry': 3, 'Fragaria': 3,
    'Blueberry': 3, 'Vaccinium': 3,
    'Raspberry': 3, 'Rubus': 3,
    'Cranberry': 3, 'Vaccinium Macrocarpon': 3,
    'Acai': 3, 'Euterpe Oleracea': 3,
    'Goji': 3, 'Lycium Barbarum': 3,

    # Tier 4: Herbs, flowers, specialty plants
    'Rose': 4, 'Rosa': 4,
    'Lavender': 4, 'Lavandula': 4,
    'Chamomile': 4, 'Anthemis Nobilis': 4, 'Matricaria': 4,
    'Aloe': 4, 'Aloe Vera': 4, 'Aloe Barbadensis': 4,
    'Green Tea': 4, 'Camellia Sinensis': 4,
    'Camellia': 4,
    'Rosemary': 4, 'Rosmarinus Officinalis': 4,
    'Eucalyptus': 4,
    'Peppermint': 4, 'Mentha Piperita': 4,
    'Tea Tree': 4, 'Melaleuca Alternifolia': 4, 'Melaleuca': 4,
    'Vanilla': 4, 'Vanilla Planifolia': 4,
    'Ginger': 4, 'Zingiber Officinale': 4,
    'Turmeric': 4, 'Curcuma Longa': 4,
    'Jasmine': 4, 'Jasminum': 4,
    'Ylang Ylang': 4, 'Cananga Odorata': 4,
    'Honey': 4, 'Mel': 4,
    'Beeswax': 4, 'Cera Alba': 4,
    'Algae': 4, 'Seaweed': 4, 'Kelp': 4,
    'Bamboo': 4,

    # Tier 5: Derived compounds (acids, alcohols, glycerin)
    'Glycerin': 5, 'Vegetable Glycerin': 5,
    'Lauric Acid': 5,
    'Stearic Acid': 5,
    'Oleic Acid': 5,
    'Linoleic Acid': 5,
    'Myristic Acid': 5,
    'Caprylic Acid': 5,
    'Capric Acid': 5,
    'Behenic Acid': 5,
    'Cetyl Alcohol': 5,
    'Cetearyl Alcohol': 5,
    'Lanolin': 5,
    'Glucose': 5,
    'Glycol': 5,
    'Various Oils': 5,

    # Tier 6: Minerals and amino acids (least visually distinctive)
    'Salt': 6, 'Sodium Chloride': 6,
    'Potassium': 6,
    'Glutamic Acid': 6,
    'Glycine': 6, 'Amino Acid': 6,
    'Alanine': 6,
    'Arginine': 6,
    'Lysine': 6,
    'Proline': 6,
    'Malic Acid': 6,
    'Fruit Sugar': 6,
}

# Default priority for unknown sources
DEFAULT_PRIORITY = 4

MAX_SOURCES = 6  # Maximum number of sources to return


def prioritize_sources(sources: List[str]) -> List[str]:
    """
    Sort sources by priority and return top MAX_SOURCES.

    Priority: Primary plants > Seeds/nuts > Fruits > Herbs > Acids > Minerals
    """
    if not sources:
        return []

    # Score each source
    scored = []
    for source in sources:
        priority = SOURCE_PRIORITY.get(source, DEFAULT_PRIORITY)
        scored.append((source, priority))

    # Sort by priority (lower = better), then alphabetically
    scored.sort(key=lambda x: (x[1], x[0]))

    # Return top sources, removing duplicates while preserving order
    seen = set()
    result = []
    for source, _ in scored:
        # Skip if we've seen a very similar source
        source_lower = source.lower()
        skip = False
        for s in seen:
            # Skip duplicates like "Coconut" and "Cocos Nucifera"
            if source_lower in s or s in source_lower:
                skip = True
                break

        if not skip:
            seen.add(source_lower)
            result.append(source)

        if len(result) >= MAX_SOURCES:
            break

    return result


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def normalize_text(text: str) -> str:
    """Normalize text for matching."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_plant_sources(ingredient_name: str) -> List[str]:
    """
    Extract plant sources from an ingredient name.

    Examples:
        "Sodium Cocoyl/Palmoyl/Sunfloweroyl Glutamate"
        → ['Sodium', 'Coconut', 'Palm', 'Sunflower', 'Glutamic Acid']

        "Sodium Macadamiaseedate"
        → ['Sodium', 'Macadamia', 'Macadamia Seed']
    """
    sources = set()

    # Normalize ingredient name
    name_lower = ingredient_name.lower()

    # Remove common non-source words for cleaner matching
    cleaned = re.sub(r'\b(copolymer|crosspolymer|polymer|acrylates?|methacrylates?)\b', '', name_lower)

    # Short prefixes that need word boundary or specific context matching
    # to avoid false positives (e.g., 'oat' in 'cocoate')
    short_prefixes = {'oat', 'soy', 'corn', 'rice', 'palm', 'date'}

    # Check each chemical prefix
    for prefix, plant_sources in CHEMICAL_TO_PLANT.items():
        if not plant_sources:  # Skip empty source lists
            continue

        # For short prefixes, use word boundary matching
        if prefix in short_prefixes:
            if re.search(rf'\b{prefix}\b', cleaned) or re.search(rf'\b{prefix}[a-z]{{0,3}}\b', cleaned):
                # Avoid false positives like 'cocoate' matching 'oat'
                if prefix == 'oat' and 'cocoate' in cleaned:
                    continue
                if prefix == 'date' and ('seedate' in cleaned or 'update' in cleaned):
                    continue
                sources.update(plant_sources[:2])
        elif prefix in cleaned:
            sources.update(plant_sources[:2])

    # Also check for direct plant names in the ingredient (with word boundaries)
    direct_plants = [
        'coconut', 'sunflower', 'olive', 'almond', 'macadamia', 'shea',
        'jojoba', 'castor', 'safflower', 'rapeseed', 'canola', 'cotton',
        'avocado', 'argan', 'sesame', 'grape', 'lemon', 'orange', 'apple',
        'rose', 'lavender', 'cocoa', 'sugar', 'honey', 'aloe', 'vanilla',
        'ginger', 'chamomile', 'wheat', 'soybean', 'bamboo', 'cucumber',
        'tomato', 'carrot', 'pomegranate', 'mango', 'papaya', 'pineapple',
        'banana', 'kiwi', 'peach', 'apricot', 'plum', 'cherry', 'fig',
        'strawberry', 'blueberry', 'raspberry', 'cranberry', 'acai',
    ]

    for plant in direct_plants:
        if re.search(rf'\b{plant}\b', name_lower) or plant in name_lower.replace(' ', ''):
            # Get the mapped sources
            if plant in CHEMICAL_TO_PLANT:
                sources.update(CHEMICAL_TO_PLANT[plant][:2])
            else:
                sources.add(plant.title())

    # Prioritize and limit sources
    return prioritize_sources(list(sources))


def find_matching_image_folders(plant_source: str, available_folders: List[str]) -> List[str]:
    """
    Find image folders that match a plant source.
    Uses fuzzy matching for flexibility.
    """
    matches = []
    source_normalized = normalize_text(plant_source)
    source_words = set(source_normalized.split())

    for folder in available_folders:
        folder_normalized = normalize_text(folder)
        folder_words = set(folder_normalized.split())

        # Exact match
        if source_normalized in folder_normalized or folder_normalized in source_normalized:
            matches.append((folder, 1.0))
            continue

        # Word overlap
        overlap = source_words & folder_words
        if overlap and len(overlap) >= min(len(source_words), 1):
            score = len(overlap) / max(len(source_words), len(folder_words))
            if score >= 0.3:
                matches.append((folder, score))
                continue

        # Fuzzy string match
        ratio = SequenceMatcher(None, source_normalized, folder_normalized).ratio()
        if ratio >= 0.6:
            matches.append((folder, ratio))

    # Sort by score and return folder names
    matches.sort(key=lambda x: x[1], reverse=True)
    return [m[0] for m in matches[:3]]  # Return top 3 matches


# Keywords that indicate "in the field" natural images (preferred)
NATURAL_IMAGE_KEYWORDS = [
    'field', 'plant', 'tree', 'growing', 'nature', 'natural', 'farm', 'garden',
    'outdoor', 'wild', 'harvest', 'branch', 'leaf', 'flower', 'bloom', 'fresh',
    'organic', 'raw', 'whole', 'fruit', 'seed', 'nut', 'pod', 'grove', 'orchard',
]

# Keywords that indicate studio/isolated images (less preferred for compounds)
STUDIO_IMAGE_KEYWORDS = [
    'white', 'transparent', 'isolated', 'cutout', 'png', 'background', 'studio',
    'glossary', 'page', 'icon', 'logo', 'vector', 'illustration', 'graphic',
]


def score_image_naturalness(image_path: str) -> int:
    """
    Score an image based on whether it appears to be a natural/field image.
    Higher score = more natural/preferred.

    Returns:
        2 = Likely natural/field image
        1 = Neutral
        0 = Likely studio/isolated image
    """
    path_lower = image_path.lower()
    filename = Path(image_path).stem.lower()

    # Check for natural keywords (boost score)
    natural_count = sum(1 for kw in NATURAL_IMAGE_KEYWORDS if kw in path_lower)

    # Check for studio keywords (reduce score)
    studio_count = sum(1 for kw in STUDIO_IMAGE_KEYWORDS if kw in path_lower)

    # PNG files are often isolated/transparent background
    if path_lower.endswith('.png'):
        studio_count += 1

    # JPEG files are more likely to be photographs
    if path_lower.endswith(('.jpg', '.jpeg')):
        natural_count += 0.5

    # Calculate score
    if natural_count > studio_count:
        return 2
    elif studio_count > natural_count:
        return 0
    else:
        return 1


def prioritize_images(image_paths: List[str], prefer_natural: bool = True) -> List[str]:
    """
    Sort images by preference, with natural/field images first.

    Args:
        image_paths: List of image file paths
        prefer_natural: If True, prefer in-the-field images over studio shots

    Returns:
        Sorted list of image paths
    """
    if not prefer_natural or not image_paths:
        return image_paths

    # Score each image
    scored = [(path, score_image_naturalness(path)) for path in image_paths]

    # Sort by score (higher first), then by path
    scored.sort(key=lambda x: (-x[1], x[0]))

    return [path for path, _ in scored]


def get_pubchem_image_url(ingredient_name: str, cas_number: str = None) -> Optional[str]:
    """Get molecular structure image URL from PubChem."""
    cid = None

    # Try CAS number first
    if cas_number:
        try:
            url = f"{PUBCHEM_API}/compound/name/{quote(cas_number)}/cids/JSON"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                cids = data.get('IdentifierList', {}).get('CID', [])
                if cids:
                    cid = cids[0]
        except Exception:
            pass

    # Try ingredient name
    if not cid:
        search_name = ingredient_name
        search_name = re.sub(r'\s*\([^)]*\)\s*', ' ', search_name)
        search_name = re.sub(r'\s+(extract|oil|water|juice|powder|butter).*$', '', search_name, flags=re.IGNORECASE)
        search_name = search_name.strip()

        if search_name:
            try:
                url = f"{PUBCHEM_API}/compound/name/{quote(search_name)}/cids/JSON"
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    cids = data.get('IdentifierList', {}).get('CID', [])
                    if cids:
                        cid = cids[0]
            except Exception:
                pass

    if cid:
        return f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG?image_size=300x300"

    return None


def get_available_image_folders() -> List[str]:
    """Get list of available image folders from master directory."""
    folders = []

    if LOCAL_MASTER.exists():
        for item in LOCAL_MASTER.iterdir():
            if item.is_dir():
                folders.append(item.name)

    return folders


def get_plant_derived_synthetic_ingredients() -> List[Dict]:
    """Get plant-derived synthetic ingredients from the missing images file."""
    file_path = PROJECT_DIR / "missing_images_PLANT_DERIVED_SYNTHETIC.txt"

    ingredients = []

    if file_path.exists():
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip headers, empty lines, and info lines
                if not line or line.startswith('=') or line.startswith('-') or line.startswith('Image Strategy') or line.startswith('•') or line.startswith('PLANT'):
                    continue
                # Skip numeric prefix if present
                if re.match(r'^\d+\.\s*', line):
                    continue
                ingredients.append({'inci_name': line})

    return ingredients


# =============================================================================
# MAIN MATCHING LOGIC
# =============================================================================

def match_ingredient_to_images(ingredient_name: str, available_folders: List[str]) -> Dict:
    """
    Match an ingredient to its source images.

    Returns:
        {
            'ingredient': str,
            'hero_image': str (PubChem URL or placeholder),
            'source_plants': [str],
            'matched_folders': [str],
            'all_images': [str]  # Paths to actual image files
        }
    """
    result = {
        'ingredient': ingredient_name,
        'hero_image': None,
        'source_plants': [],
        'matched_folders': [],
        'all_images': []
    }

    # 1. Get PubChem molecular structure for hero image
    hero_url = get_pubchem_image_url(ingredient_name)
    result['hero_image'] = hero_url if hero_url else PLACEHOLDER_URL

    # 2. Extract plant sources from ingredient name
    sources = extract_plant_sources(ingredient_name)
    result['source_plants'] = sources

    # 3. Find matching image folders for each source
    matched_folders = set()
    for source in sources:
        matches = find_matching_image_folders(source, available_folders)
        matched_folders.update(matches)

    result['matched_folders'] = list(matched_folders)

    # 4. Collect actual image files from matched folders
    all_images = []
    for folder_name in matched_folders:
        folder_path = LOCAL_MASTER / folder_name
        if folder_path.exists():
            for img_file in folder_path.iterdir():
                if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                    all_images.append(str(img_file))

    # Prioritize natural/field images over studio shots
    # This helps show where ingredients come from
    all_images = prioritize_images(all_images, prefer_natural=True)

    result['all_images'] = all_images[:10]  # Limit to 10 images

    return result


def process_all_ingredients(dry_run: bool = True, limit: int = None) -> List[Dict]:
    """Process all plant-derived synthetic ingredients."""

    print("=" * 70)
    print("PLANT-DERIVED SYNTHETIC INGREDIENT IMAGE MATCHER")
    print("=" * 70)
    print()

    # Get available image folders
    print("Loading available image folders...")
    available_folders = get_available_image_folders()
    print(f"  Found {len(available_folders)} image folders")
    print()

    # Get ingredients to process
    print("Loading plant-derived synthetic ingredients...")
    ingredients = get_plant_derived_synthetic_ingredients()

    if limit:
        ingredients = ingredients[:limit]

    print(f"  Processing {len(ingredients)} ingredients")
    print()

    results = []

    for i, ing in enumerate(ingredients, 1):
        name = ing['inci_name']

        # Skip very short or clearly non-ingredient lines
        if len(name) < 3 or name.startswith('(') or '======' in name:
            continue

        result = match_ingredient_to_images(name, available_folders)
        results.append(result)

        if i <= 20 or i % 100 == 0:
            sources_str = ', '.join(result['source_plants'][:4]) if result['source_plants'] else 'None found'
            folders_str = ', '.join(result['matched_folders'][:3]) if result['matched_folders'] else 'None'
            hero_status = "PubChem" if result['hero_image'] != PLACEHOLDER_URL else "Placeholder"

            print(f"[{i}] {name[:50]}")
            print(f"    Sources ({len(result['source_plants'])}): {sources_str}")
            print(f"    Folders: {folders_str}")
            print(f"    Hero: {hero_status}, Images: {len(result['all_images'])}")
            print()

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    with_pubchem = sum(1 for r in results if r['hero_image'] != PLACEHOLDER_URL)
    with_sources = sum(1 for r in results if r['source_plants'])
    with_images = sum(1 for r in results if r['all_images'])

    print(f"Total ingredients processed: {len(results)}")
    print(f"With PubChem structure:      {with_pubchem} ({100*with_pubchem/len(results):.1f}%)")
    print(f"With identified sources:     {with_sources} ({100*with_sources/len(results):.1f}%)")
    print(f"With matched images:         {with_images} ({100*with_images/len(results):.1f}%)")
    print()

    if dry_run:
        print("[DRY RUN] No changes made.")
        print("Run with --live to apply changes.")

    return results


def save_results(results: List[Dict], output_path: Path = None):
    """Save matching results to JSON file."""
    if output_path is None:
        output_path = PROJECT_DIR / "plant_derived_image_matches.json"

    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to: {output_path}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys

    dry_run = '--live' not in sys.argv
    limit = None

    for arg in sys.argv:
        if arg.startswith('--limit='):
            try:
                limit = int(arg.split('=')[1])
            except:
                pass

    results = process_all_ingredients(dry_run=dry_run, limit=limit)

    # Save results
    save_results(results)
