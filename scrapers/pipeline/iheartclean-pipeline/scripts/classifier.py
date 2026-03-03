#!/usr/bin/env python3
"""
Local 9S Classifier for iHeartClean.beauty
No API calls - 100% FREE classification using regex patterns.
"""

import re
from typing import Dict, List, Tuple, Optional

# ============================================================================
# ATTRIBUTE DETECTION PATTERNS
# ============================================================================

PATTERNS = {
    "SAFETY": {
        "clean": r"clean\s*(beauty|formula|ingredients?)",
        "non_toxic": r"non[\-\s]?toxic|toxin[\-\s]?free",
        "ewg_verified": r"ewg\s*(verified|certified|\d)",
        "fragrance_free": r"fragrance[\-\s]?free|unscented|no\s*fragrance|sans\s*parfum",
        "hypoallergenic": r"hypo[\-\s]?allergenic",
        "pregnancy_safe": r"pregnancy[\-\s]?safe|safe\s*(for|during)\s*pregnancy|expecting\s*mothers?",
        "nursing_safe": r"nursing[\-\s]?safe|breastfeeding[\-\s]?safe",
        "baby_safe": r"baby[\-\s]?safe|infant[\-\s]?safe|safe\s*for\s*bab(y|ies)",
        "paraben_free": r"paraben[\-\s]?free|no\s*parabens?",
        "sulfate_free": r"sulfate[\-\s]?free|sls[\-\s]?free|no\s*sulfates?",
        "phthalate_free": r"phthalate[\-\s]?free|no\s*phthalates?",
        "silicone_free": r"silicone[\-\s]?free|no\s*silicones?",
        "mineral_based": r"mineral[\-\s]?(based|formula|sunscreen)|100%\s*mineral",
        "gluten_free": r"gluten[\-\s]?free",
        "nut_free": r"nut[\-\s]?free|tree\s*nut[\-\s]?free",
        "soy_free": r"soy[\-\s]?free",
        "dermatologist_tested": r"dermatologist[\s\-\w]*(tested|approved|recommended)|derm[\-\s]?tested",
        "allergy_tested": r"allergy[\-\s]?tested|clinically\s*tested\s*for\s*allergies",
        "oncologist_approved": r"oncologist[\-\s]?(approved|recommended|tested)|chemo[\-\s]?safe",
        "no_synthetic_fragrance": r"no\s*synthetic\s*fragrance|natural\s*fragrance\s*only",
    },
    "SOURCE": {
        "dermatologist_developed": r"dermatologist[\-\s]?(developed|created|formulated)",
        "medical_grade": r"medical[\-\s]?grade|pharmaceutical[\-\s]?grade|clinical[\-\s]?grade",
        "woman_owned": r"woman[\-\s]?owned|female[\-\s]?founded|women[\-\s]?led",
        "black_owned": r"black[\-\s]?owned|african[\-\s]?american[\-\s]?owned",
        "aapi_owned": r"aapi[\-\s]?owned|asian[\-\s]?owned|asian[\-\s]?american",
        "latinx_owned": r"latin[xao][\-\s]?owned|hispanic[\-\s]?owned",
        "lgbtq_owned": r"lgbtq\+?[\-\s]?owned|queer[\-\s]?owned|pride[\-\s]?owned",
        "indie_brand": r"indie\s*brand|independent\s*brand|small\s*batch",
        "family_owned": r"family[\-\s]?owned|family[\-\s]?run",
        "made_in_usa": r"made\s*in\s*(the\s*)?(usa|u\.?s\.?a?\.?|america|united\s*states)",
        "made_in_korea": r"made\s*in\s*korea|k[\-\s]?beauty|korean\s*beauty",
        "made_in_france": r"made\s*in\s*france|french\s*beauty",
        "b_corp": r"b[\-\s]?corp|certified\s*b\s*corporation",
        "transparent_sourcing": r"transparent\s*sourc|ethically\s*sourced|responsibly\s*sourced",
    },
    "STARS": {
        "clinically_proven": r"clinically\s*(proven|tested|shown)|clinical\s*(trials?|studies|results)",
        "award_winning": r"award[\-\s]?winning|won\s*(\d+\s*)?awards?|best\s*of\s*beauty",
        "best_seller": r"best[\-\s]?seller|#?\d+\s*seller|top[\-\s]?selling",
        "trending": r"trending|viral|tiktok\s*famous",
        "top_rated": r"top[\-\s]?rated|highly\s*rated",
        "customer_favorite": r"customer\s*favorite|fan\s*favorite|cult\s*favorite",
        "expert_recommended": r"expert[\-\s]?recommended|recommended\s*by\s*(experts?|professionals?)",
        "editors_choice": r"editor'?s?\s*choice|editor'?s?\s*pick",
        "influencer_pick": r"influencer\s*(pick|favorite|recommended)",
        "community_choice": r"community\s*(choice|favorite|pick)",
    },
    "SUSTAINABILITY": {
        "vegan": r"\bvegan\b|100%\s*vegan|plant[\-\s]?based\s*formula",
        "cruelty_free": r"cruelty[\-\s]?free|not\s*tested\s*on\s*animals|no\s*animal\s*testing",
        "leaping_bunny": r"leaping\s*bunny|peta[\-\s]?certified",
        "organic": r"\borganic\b|usda\s*organic|certified\s*organic",
        "sustainably_sourced": r"sustainably\s*sourced|sustainable\s*ingredients?",
        "carbon_neutral": r"carbon[\-\s]?neutral|net[\-\s]?zero|climate[\-\s]?neutral",
        "zero_waste": r"zero[\-\s]?waste",
        "biodegradable": r"bio[\-\s]?degradable",
        "reef_safe": r"reef[\-\s]?safe|ocean[\-\s]?safe|coral[\-\s]?safe",
        "recyclable": r"recyclable|recycled\s*(packaging|materials?|plastic)",
        "refillable": r"refillable|refill\s*(available|system|pod)",
        "eco_packaging": r"eco[\-\s]?friendly\s*packaging|sustainable\s*packaging|pcr\s*plastic",
        "one_percent_planet": r"1%\s*for\s*(the\s*)?planet",
    },
    "SUPPORT": {
        "hydrating": r"\bhydrating\b|intense\s*hydration|deep\s*hydration",
        "moisturizing": r"\bmoisturizing\b|moisture[\-\s]?rich|ultra[\-\s]?moisturizing",
        "soothing": r"\bsoothing\b|calming|anti[\-\s]?irritation",
        "anti_inflammatory": r"anti[\-\s]?inflammatory|reduces?\s*inflammation",
        "barrier_repair": r"barrier[\-\s]?repair|skin\s*barrier|strengthens?\s*barrier",
        "long_wearing": r"long[\-\s]?wearing|all[\-\s]?day|12[\-\s]?hour|24[\-\s]?hour",
        "quick_absorbing": r"quick[\-\s]?absorbing|fast[\-\s]?absorbing|absorbs?\s*quickly",
        "non_greasy": r"non[\-\s]?greasy|oil[\-\s]?free\s*feel|lightweight\s*feel",
        "buildable": r"buildable\s*coverage|build\s*coverage",
        "full_coverage": r"full[\-\s]?coverage|maximum\s*coverage|complete\s*coverage",
        "sheer_coverage": r"sheer[\-\s]?coverage|light\s*coverage|natural\s*coverage",
        "transfer_proof": r"transfer[\-\s]?proof|no[\-\s]?transfer|won'?t\s*transfer",
        "sweat_proof": r"sweat[\-\s]?proof|sweat[\-\s]?resistant",
        "water_resistant": r"water[\-\s]?(resistant|proof)|waterproof",
    },
    "SUITABILITY": {
        "all_skin_types": r"all\s*skin\s*types|every\s*skin\s*type|universal",
        "sensitive_skin": r"(for\s*)?sensitive\s*skin|gentle\s*(for|on)\s*sensitive",
        "dry_skin": r"(for\s*)?dry\s*skin|intense\s*moisture\s*for\s*dry",
        "oily_skin": r"(for\s*)?oily\s*skin|oil[\-\s]?control|mattifying",
        "combination_skin": r"combination\s*skin",
        "mature_skin": r"mature\s*skin|aging\s*skin|anti[\-\s]?aging",
        "acne_prone": r"acne[\-\s]?prone|blemish[\-\s]?prone|non[\-\s]?comedogenic",
        "rosacea": r"rosacea[\-\s]?prone|rosacea[\-\s]?safe|good\s*for\s*rosacea",
        "eczema": r"eczema[\-\s]?prone|eczema[\-\s]?safe|good\s*for\s*eczema",
        "melanin_rich": r"melanin[\-\s]?rich|deeper?\s*skin\s*tones?|dark\s*skin",
        "textured_hair": r"textured\s*hair|coily\s*hair|4[abc]\s*hair|type\s*4",
        "curly_hair": r"curly\s*hair|curls|3[abc]\s*hair|type\s*3",
        "color_treated": r"color[\-\s]?treated|dyed\s*hair|colored\s*hair",
        "teen_friendly": r"teen|teenage|young\s*skin|first\s*skincare",
        "postpartum": r"postpartum|post[\-\s]?pregnancy|new\s*mom",
        "menopause": r"menopause|menopausal|perimenopause",
        "shade_range_40": r"40\+?\s*shades?|50\+?\s*shades?|60\s*shades?|extensive\s*shade",
    },
    "STRUCTURE": {
        "pump": r"\bpump\b|pump\s*bottle",
        "airless_pump": r"airless\s*pump",
        "dropper": r"\bdropper\b|glass\s*dropper|pipette",
        "tube": r"\btube\b|squeeze\s*tube",
        "jar": r"\bjar\b|glass\s*jar|pot",
        "spray": r"\bspray\b|mist\s*bottle|spritz",
        "stick": r"\bstick\b|balm\s*stick",
        "travel_size": r"travel[\-\s]?size|mini|on[\-\s]?the[\-\s]?go|portable",
        "value_size": r"value[\-\s]?size|jumbo|family[\-\s]?size|large\s*size",
        "refillable_pkg": r"refillable|refill\s*cartridge",
    },
    "SUBSTANCE": {
        "serum": r"\bserum\b",
        "cream": r"\bcream\b|crème",
        "gel": r"\bgel\b|gel[\-\s]?cream",
        "oil": r"\boil\b|face\s*oil|body\s*oil",
        "balm": r"\bbalm\b",
        "lotion": r"\blotion\b",
        "mist": r"\bmist\b|facial\s*spray",
        "retinol": r"\bretinol\b|retinoid|vitamin\s*a\b",
        "vitamin_c": r"vitamin\s*c\b|l[\-\s]?ascorbic|ascorbic\s*acid",
        "niacinamide": r"\bniacinamide\b|vitamin\s*b3\b",
        "hyaluronic_acid": r"hyaluronic\s*acid|sodium\s*hyaluronate",
        "peptides": r"\bpeptides?\b|copper\s*peptide|matrixyl",
        "aha_bha": r"\baha\b|\bbha\b|glycolic|salicylic|lactic\s*acid",
        "spf": r"\bspf\s*\d+|sun\s*protection|sunscreen|sunblock",
        "zinc_oxide": r"zinc\s*oxide|mineral\s*sunscreen",
        "ceramides": r"\bceramides?\b",
        "centella": r"centella|cica|tiger\s*grass|gotu\s*kola",
        "bakuchiol": r"\bbakuchiol\b",
        "squalane": r"\bsqualane\b|\bsqualene\b",
        "aloe": r"\baloe\b|aloe\s*vera",
        "collagen": r"\bcollagen\b",
        "caffeine": r"\bcaffeine\b",
    },
    "SPEND": {
        "drugstore": r"drugstore|pharmacy|budget[\-\s]?friendly",
        "prestige": r"prestige|luxury|premium|high[\-\s]?end",
        "subscription": r"subscription|auto[\-\s]?replenish|subscribe\s*&?\s*save",
        "sample_available": r"sample|trial\s*size|try\s*before",
        "value_set": r"value\s*set|bundle|kit\s*includes|gift\s*set",
    },
}

# ============================================================================
# PERSONA PRIORITIES (Research-backed)
# ============================================================================

PERSONA_PRIORITIES = {
    "antiaging_pro": {
        1: ["clinically_proven", "retinol", "vitamin_c", "peptides", "hyaluronic_acid", 
            "spf", "serum", "dermatologist_developed", "mature_skin", "menopause"],
        2: ["dermatologist_tested", "expert_recommended", "medical_grade", "clean", 
            "non_toxic", "paraben_free", "hydrating", "moisturizing", "barrier_repair",
            "long_wearing", "cream", "aha_bha", "ceramides", "bakuchiol", "collagen",
            "cruelty_free", "transparent_sourcing", "top_rated", "airless_pump"],
    },
    "family_mom": {
        1: ["ewg_verified", "pregnancy_safe", "nursing_safe", "baby_safe", "non_toxic",
            "clean", "paraben_free", "phthalate_free", "value_size", "hypoallergenic",
            "postpartum", "bakuchiol", "spf", "zinc_oxide"],
        2: ["dermatologist_tested", "fragrance_free", "sulfate_free", "nut_free",
            "made_in_usa", "family_owned", "woman_owned", "hydrating", "moisturizing",
            "soothing", "barrier_repair", "sensitive_skin", "dry_skin", "eczema",
            "all_skin_types", "pump", "tube", "cream", "balm", "lotion", "vegan",
            "cruelty_free", "organic", "eco_packaging", "subscription", "value_set",
            "teen_friendly", "vitamin_c"],
    },
    "cancer_sensitive": {
        1: ["oncologist_approved", "dermatologist_developed", "medical_grade",
            "fragrance_free", "hypoallergenic", "dermatologist_tested", "clean",
            "non_toxic", "ewg_verified", "paraben_free", "sulfate_free", "phthalate_free",
            "no_synthetic_fragrance", "mineral_based", "allergy_tested", "hydrating",
            "moisturizing", "soothing", "anti_inflammatory", "barrier_repair",
            "sensitive_skin", "dry_skin", "rosacea", "eczema", "pump", "airless_pump",
            "cream", "balm", "hyaluronic_acid", "ceramides", "centella", "aloe",
            "spf", "zinc_oxide"],
        2: ["silicone_free", "gluten_free", "nut_free", "soy_free", "clinically_proven",
            "expert_recommended", "transparent_sourcing", "vegan", "cruelty_free",
            "serum", "oil", "mist"],
    },
    "bipoc_inclusive_fluid": {
        1: ["shade_range_40", "melanin_rich", "vitamin_c", "niacinamide", "black_owned",
            "woman_owned", "lgbtq_owned", "community_choice", "buildable", "full_coverage",
            "textured_hair", "curly_hair", "spf", "cruelty_free"],
        2: ["aapi_owned", "latinx_owned", "indie_brand", "vegan", "b_corp",
            "transparent_sourcing", "clinically_proven", "dermatologist_tested", 
            "dermatologist_developed", "medical_grade", "clean", "non_toxic", 
            "ewg_verified", "paraben_free", "sulfate_free", "silicone_free", 
            "hydrating", "moisturizing", "soothing", "barrier_repair", "sheer_coverage",
            "long_wearing", "transfer_proof", "sweat_proof", "water_resistant",
            "sensitive_skin", "acne_prone", "color_treated", "all_skin_types", 
            "pump", "dropper", "serum", "cream", "gel", "oil", "mist",
            "aha_bha", "zinc_oxide", "ceramides", "caffeine", "hyaluronic_acid",
            "carbon_neutral", "zero_waste", "biodegradable", "reef_safe", 
            "eco_packaging", "refillable", "one_percent_planet", "drugstore", "value_set"],
    },
    "genz": {
        1: ["trending", "niacinamide", "cruelty_free", "vegan", "leaping_bunny",
            "sustainably_sourced", "carbon_neutral", "zero_waste", "biodegradable",
            "reef_safe", "eco_packaging", "refillable", "recyclable",
            "one_percent_planet", "drugstore", "sample_available", "travel_size",
            "value_set", "acne_prone", "teen_friendly", "made_in_korea", "b_corp"],
        2: ["influencer_pick", "community_choice", "best_seller", "customer_favorite",
            "clinically_proven", "expert_recommended", "top_rated", "indie_brand",
            "woman_owned", "black_owned", "lgbtq_owned", "clean", "non_toxic",
            "paraben_free", "sulfate_free", "hydrating", "moisturizing", "buildable",
            "sheer_coverage", "long_wearing", "transfer_proof", "sweat_proof",
            "water_resistant", "all_skin_types", "oily_skin", "combination_skin",
            "melanin_rich", "curly_hair", "color_treated", "pump", "dropper",
            "serum", "gel", "mist", "vitamin_c", "hyaluronic_acid", "aha_bha",
            "spf", "centella", "squalane", "caffeine", "organic", "subscription"],
    },
    "skeptic": {
        1: ["clinically_proven", "dermatologist_tested", "dermatologist_developed",
            "ewg_verified", "leaping_bunny", "medical_grade", "allergy_tested",
            "transparent_sourcing", "b_corp", "organic"],
        2: ["expert_recommended", "top_rated", "paraben_free", "phthalate_free",
            "sulfate_free", "fragrance_free", "non_toxic", "clean", "cruelty_free",
            "vegan", "made_in_usa", "recyclable", "sustainably_sourced",
            "reef_safe", "mineral_based", "hypoallergenic"],
    },
}

# ============================================================================
# CLASSIFICATION FUNCTIONS
# ============================================================================

def detect_attributes(text: str) -> Dict[str, bool]:
    """Detect all attributes using regex patterns. 100% FREE."""
    text_lower = text.lower()
    detected = {}
    
    for category, patterns in PATTERNS.items():
        for attr, pattern in patterns.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                detected[attr] = True
    
    return detected


def calculate_9s_scores(detected: Dict[str, bool], price: Optional[float] = None) -> Dict[str, int]:
    """Calculate scores for each 9S category (1-5 scale)."""
    category_attrs = {
        "stars": ["clinically_proven", "award_winning", "best_seller", "trending", 
                  "top_rated", "customer_favorite", "expert_recommended", 
                  "editors_choice", "influencer_pick", "community_choice"],
        "source": ["dermatologist_developed", "medical_grade", "woman_owned", 
                   "black_owned", "aapi_owned", "latinx_owned", "lgbtq_owned",
                   "indie_brand", "family_owned", "made_in_usa", "made_in_korea",
                   "made_in_france", "b_corp", "transparent_sourcing"],
        "safety": ["clean", "non_toxic", "ewg_verified", "fragrance_free",
                   "hypoallergenic", "pregnancy_safe", "nursing_safe", "baby_safe",
                   "paraben_free", "sulfate_free", "phthalate_free", "silicone_free",
                   "mineral_based", "gluten_free", "nut_free", "soy_free",
                   "dermatologist_tested", "allergy_tested", "oncologist_approved",
                   "no_synthetic_fragrance"],
        "support": ["hydrating", "moisturizing", "soothing", "anti_inflammatory",
                    "barrier_repair", "long_wearing", "quick_absorbing", "non_greasy",
                    "buildable", "full_coverage", "sheer_coverage", "transfer_proof",
                    "sweat_proof", "water_resistant"],
        "suitability": ["all_skin_types", "sensitive_skin", "dry_skin", "oily_skin",
                        "combination_skin", "mature_skin", "acne_prone", "rosacea",
                        "eczema", "melanin_rich", "textured_hair", "curly_hair",
                        "color_treated", "teen_friendly", "postpartum", "menopause",
                        "shade_range_40"],
        "structure": ["pump", "airless_pump", "dropper", "tube", "jar", "spray",
                      "stick", "travel_size", "value_size", "refillable_pkg"],
        "substance": ["serum", "cream", "gel", "oil", "balm", "lotion", "mist",
                      "retinol", "vitamin_c", "niacinamide", "hyaluronic_acid",
                      "peptides", "aha_bha", "spf", "zinc_oxide", "ceramides",
                      "centella", "bakuchiol", "squalane", "aloe", "collagen",
                      "caffeine"],
        "sustainability": ["vegan", "cruelty_free", "leaping_bunny", "organic",
                           "sustainably_sourced", "carbon_neutral", "zero_waste",
                           "biodegradable", "reef_safe", "recyclable", "refillable",
                           "eco_packaging", "one_percent_planet"],
        "spend": ["drugstore", "prestige", "subscription", "sample_available",
                  "value_set"],
    }
    
    scores = {}
    for category, attrs in category_attrs.items():
        matches = sum(1 for a in attrs if detected.get(a))
        total = len(attrs)
        pct = matches / total if total > 0 else 0
        
        if pct >= 0.4:
            scores[category] = 5
        elif pct >= 0.25:
            scores[category] = 4
        elif pct >= 0.15:
            scores[category] = 3
        elif pct > 0:
            scores[category] = 2
        else:
            scores[category] = 1
    
    # Adjust spend score based on price if available
    if price is not None:
        if price < 15:
            scores["spend"] = max(scores["spend"], 4)
        elif price < 30:
            scores["spend"] = max(scores["spend"], 3)
        elif price < 60:
            scores["spend"] = 3
        else:
            scores["spend"] = 2
    
    return scores


def calculate_persona_relevance(detected: Dict[str, bool]) -> Dict[str, float]:
    """Calculate relevance score (0-100) for each persona."""
    relevance = {}
    
    for persona, priorities in PERSONA_PRIORITIES.items():
        critical_attrs = priorities.get(1, [])
        high_attrs = priorities.get(2, [])
        
        critical_matches = sum(1 for a in critical_attrs if detected.get(a))
        high_matches = sum(1 for a in high_attrs if detected.get(a))
        
        critical_score = (critical_matches / max(len(critical_attrs), 1)) * 60
        high_score = (high_matches / max(len(high_attrs), 1)) * 40
        
        relevance[persona] = round(critical_score + high_score, 1)
    
    return relevance


def extract_product_data(text: str) -> Dict:
    """Extract price, size, rating from text."""
    data = {"price": None, "size": None, "rating": None, "shade_count": None}
    
    # Price
    price_match = re.search(r'\$(\d+\.?\d*)', text)
    if price_match:
        data["price"] = float(price_match.group(1))
    
    # Size
    size_match = re.search(r'(\d+\.?\d*)\s*(oz|ml|fl\.?\s*oz|g|gram)', text, re.I)
    if size_match:
        data["size"] = f"{size_match.group(1)} {size_match.group(2).lower()}"
    
    # Rating
    rating_match = re.search(r'(\d+\.?\d*)\s*(?:out\s*of\s*5|stars?|\/\s*5)', text, re.I)
    if rating_match:
        val = float(rating_match.group(1))
        data["rating"] = val if val <= 5 else None
    
    # Shade count
    shade_match = re.search(r'(\d+)\s*shades?', text, re.I)
    if shade_match:
        data["shade_count"] = int(shade_match.group(1))
    
    return data


def classify_product(text: str, product_name: str = "", brand: str = "") -> Dict:
    """
    Full classification pipeline. Returns Webflow-ready data.
    Cost: $0.00 (all local processing)
    """
    # Detect attributes
    detected = detect_attributes(text)
    
    # Extract product data
    product_data = extract_product_data(text)
    
    # Calculate scores
    scores = calculate_9s_scores(detected, product_data.get("price"))
    persona_scores = calculate_persona_relevance(detected)
    
    # Overall score
    overall = round(sum(scores.values()) / len(scores), 1)
    
    # Best for personas (>40% relevance)
    best_for = [p for p, s in persona_scores.items() if s >= 40]
    
    # Generate slug: brand-product-name format
    # Clean brand and product name, then combine
    clean_brand = brand.lower().strip() if brand else ""
    clean_name = product_name.lower().strip() if product_name else ""
    slug_text = f"{clean_brand} {clean_name}".strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug_text).strip('-')[:80]
    
    return {
        "name": product_name[:100] if product_name else "",
        "slug": slug or "product",
        "brand": brand,
        "price": product_data.get("price"),
        "size": product_data.get("size"),
        "rating": product_data.get("rating"),
        "shade_count": product_data.get("shade_count"),
        "scores": scores,
        "overall_score": overall,
        "detected_attributes": list(detected.keys()),
        "attribute_count": len(detected),
        "persona_relevance": persona_scores,
        "best_for": best_for,
        # Boolean flags for Webflow filtering
        "is_clean": detected.get("clean", False),
        "is_vegan": detected.get("vegan", False),
        "is_cruelty_free": detected.get("cruelty_free", False),
        "is_fragrance_free": detected.get("fragrance_free", False),
        "is_pregnancy_safe": detected.get("pregnancy_safe", False),
        "has_spf": detected.get("spf", False),
    }


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import json
    import sys
    
    if len(sys.argv) > 1:
        # Read from file
        with open(sys.argv[1], "r") as f:
            text = f.read()
        result = classify_product(text)
        print(json.dumps(result, indent=2))
    else:
        # Demo
        demo_text = """
        Tower 28 SunnyDays SPF 30 Tinted Sunscreen Foundation - $32
        Clean, vegan, cruelty-free. Fragrance-free and hypoallergenic.
        Dermatologist tested. Reef safe mineral sunscreen with zinc oxide.
        Available in 14 shades. Buildable coverage for all skin types.
        Great for sensitive skin. 1 oz / 30ml. 4.7 stars from 1200 reviews.
        """
        result = classify_product(demo_text, "SunnyDays SPF 30", "Tower 28")
        print(json.dumps(result, indent=2))
