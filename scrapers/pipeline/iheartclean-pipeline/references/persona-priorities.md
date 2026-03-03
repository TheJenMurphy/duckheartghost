# Persona Priority Weights

Quick reference for scoring products by persona relevance.

## Scoring Scale
- **1** = Critical (must-have, dealbreaker)
- **2** = High priority (strongly influences)
- **3** = Important (factors in)
- **4** = Nice-to-have
- **5** = Low priority/avoid

## Priority Lookup Table

```python
PERSONA_PRIORITIES = {
    "antiaging_pro": {
        # Critical (1)
        "clinically_proven": 1, "retinol": 1, "vitamin_c": 1, "peptides": 1,
        "hyaluronic_acid": 1, "spf": 1, "serum": 1, "dermatologist_developed": 1,
        "mature_skin": 1, "menopause": 1,
        # High (2)
        "dermatologist_tested": 2, "expert_recommended": 2, "medical_grade": 2,
        "clean": 2, "non_toxic": 2, "paraben_free": 2, "hydrating": 2,
        "moisturizing": 2, "barrier_repair": 2, "long_wearing": 2, "cream": 2,
        "aha_bha": 2, "ceramides": 2, "bakuchiol": 2, "collagen": 2,
        "cruelty_free": 2, "transparent_sourcing": 2, "top_rated": 2, "airless_pump": 2,
    },
    "family_mom": {
        # Critical (1)
        "ewg_verified": 1, "pregnancy_safe": 1, "nursing_safe": 1, "baby_safe": 1,
        "pediatrician_tested": 1, "non_toxic": 1, "clean": 1, "paraben_free": 1,
        "phthalate_free": 1, "value_size": 1, "affordable": 1, "hypoallergenic": 1,
        "postpartum": 1, "bakuchiol": 1, "spf": 1, "zinc_oxide": 1,
        # High (2)
        "dermatologist_tested": 2, "fragrance_free": 2, "sulfate_free": 2,
        "nut_free": 2, "made_in_usa": 2, "family_owned": 2, "woman_owned": 2,
        "hydrating": 2, "moisturizing": 2, "soothing": 2, "barrier_repair": 2,
        "sensitive_skin": 2, "dry_skin": 2, "eczema": 2, "all_skin_types": 2,
        "pump": 2, "tube": 2, "cream": 2, "balm": 2, "lotion": 2,
        "vegan": 2, "cruelty_free": 2, "organic": 2, "eco_packaging": 2,
        "subscription": 2, "value_set": 2, "teen_friendly": 2, "vitamin_c": 2,
    },
    "cancer_sensitive": {
        # Critical (1)
        "oncologist_approved": 1, "dermatologist_developed": 1, "medical_grade": 1,
        "fragrance_free": 1, "hypoallergenic": 1, "dermatologist_tested": 1,
        "clean": 1, "non_toxic": 1, "ewg_verified": 1, "paraben_free": 1,
        "sulfate_free": 1, "phthalate_free": 1, "no_synthetic_fragrance": 1,
        "mineral_based": 1, "allergy_tested": 1, "hydrating": 1, "moisturizing": 1,
        "soothing": 1, "calming": 1, "anti_inflammatory": 1, "barrier_repair": 1,
        "sensitive_skin": 1, "dry_skin": 1, "rosacea": 1, "eczema": 1,
        "pump": 1, "airless_pump": 1, "cream": 1, "balm": 1,
        "hyaluronic_acid": 1, "ceramides": 1, "centella": 1, "aloe": 1,
        "spf": 1, "zinc_oxide": 1,
        # High (2)
        "silicone_free": 2, "gluten_free": 2, "nut_free": 2, "soy_free": 2,
        "clinically_proven": 2, "expert_recommended": 2, "transparent_sourcing": 2,
        "vegan": 2, "cruelty_free": 2, "serum": 2, "oil": 2, "mist": 2,
    },
    "bipoc_inclusive": {
        # Critical (1)
        "shade_range_40": 1, "melanin_rich": 1, "vitamin_c": 1, "niacinamide": 1,
        "black_owned": 1, "woman_owned": 1, "community_choice": 1,
        "buildable": 1, "full_coverage": 1, "textured_hair": 1, "curly_hair": 1,
        "spf": 1,
        # High (2)
        "aapi_owned": 2, "latinx_owned": 2, "indie_brand": 2, "clinically_proven": 2,
        "dermatologist_tested": 2, "dermatologist_developed": 2, "medical_grade": 2,
        "clean": 2, "non_toxic": 2, "ewg_verified": 2, "paraben_free": 2,
        "sulfate_free": 2, "silicone_free": 2, "hydrating": 2, "moisturizing": 2,
        "soothing": 2, "barrier_repair": 2, "long_wearing": 2, "transfer_proof": 2,
        "sensitive_skin": 2, "acne_prone": 2, "color_treated": 2, "all_skin_types": 2,
        "pump": 2, "serum": 2, "cream": 2, "gel": 2, "oil": 2,
        "aha_bha": 2, "zinc_oxide": 2, "ceramides": 2, "caffeine": 2,
        "vegan": 2, "cruelty_free": 2, "sustainably_sourced": 2, "reef_safe": 2,
        "drugstore": 2, "affordable": 2, "value_set": 2,
    },
    "fluid": {
        # Critical (1)
        "cruelty_free": 1, "lgbtq_owned": 1,
        # High (2)
        "vegan": 2, "woman_owned": 2, "indie_brand": 2, "black_owned": 2,
        "aapi_owned": 2, "latinx_owned": 2, "b_corp": 2, "transparent_sourcing": 2,
        "clean": 2, "non_toxic": 2, "paraben_free": 2, "sulfate_free": 2,
        "hydrating": 2, "moisturizing": 2, "buildable": 2, "sheer_coverage": 2,
        "long_wearing": 2, "transfer_proof": 2, "sweat_proof": 2, "water_resistant": 2,
        "all_skin_types": 2, "melanin_rich": 2, "acne_prone": 2, "curly_hair": 2,
        "pump": 2, "dropper": 2, "serum": 2, "gel": 2, "mist": 2,
        "vitamin_c": 2, "niacinamide": 2, "hyaluronic_acid": 2, "spf": 2,
        "carbon_neutral": 2, "zero_waste": 2, "biodegradable": 2, "reef_safe": 2,
        "eco_packaging": 2, "refillable": 2, "one_percent_planet": 2,
    },
    "genz": {
        # Critical (1)
        "trending": 1, "viral": 1, "niacinamide": 1, "cruelty_free": 1, "vegan": 1,
        "leaping_bunny": 1, "sustainably_sourced": 1, "carbon_neutral": 1,
        "zero_waste": 1, "biodegradable": 1, "reef_safe": 1, "eco_packaging": 1,
        "refillable": 1, "recyclable": 1, "one_percent_planet": 1,
        "drugstore": 1, "affordable": 1, "sample_available": 1, "mini": 1, "value_set": 1,
        "acne_prone": 1, "teen_friendly": 1, "made_in_korea": 1, "b_corp": 1,
        # High (2)
        "influencer_pick": 2, "community_choice": 2, "best_seller": 2, "customer_favorite": 2,
        "clinically_proven": 2, "expert_recommended": 2, "top_rated": 2,
        "indie_brand": 2, "woman_owned": 2, "black_owned": 2, "lgbtq_owned": 2,
        "clean": 2, "non_toxic": 2, "paraben_free": 2, "sulfate_free": 2,
        "hydrating": 2, "moisturizing": 2, "buildable": 2, "sheer_coverage": 2,
        "long_wearing": 2, "transfer_proof": 2, "sweat_proof": 2, "water_resistant": 2,
        "all_skin_types": 2, "oily_skin": 2, "combination_skin": 2, "melanin_rich": 2,
        "curly_hair": 2, "color_treated": 2, "pump": 2, "travel_size": 2, "dropper": 2,
        "serum": 2, "gel": 2, "mist": 2, "vitamin_c": 2, "hyaluronic_acid": 2,
        "aha_bha": 2, "spf": 2, "centella": 2, "squalane": 2, "caffeine": 2,
        "organic": 2, "subscription": 2,
    },
}
```

## Persona Relevance Score Calculation

```python
def calculate_persona_relevance(detected_attributes: dict, persona: str) -> float:
    """
    Calculate how relevant a product is for a specific persona.
    Returns score 0-100 where higher = more relevant.
    """
    priorities = PERSONA_PRIORITIES.get(persona, {})
    
    critical_matches = 0  # Score 1 attributes
    critical_total = sum(1 for v in priorities.values() if v == 1)
    
    high_matches = 0  # Score 2 attributes
    high_total = sum(1 for v in priorities.values() if v == 2)
    
    for attr, detected in detected_attributes.items():
        if detected and attr in priorities:
            if priorities[attr] == 1:
                critical_matches += 1
            elif priorities[attr] == 2:
                high_matches += 1
    
    # Weighted scoring: critical=3x weight, high=1x weight
    if critical_total == 0 and high_total == 0:
        return 0
    
    critical_score = (critical_matches / max(critical_total, 1)) * 60  # 60% weight
    high_score = (high_matches / max(high_total, 1)) * 40  # 40% weight
    
    return round(critical_score + high_score, 1)
```

## Quick Reference: Top 5 Per Persona

| Persona | Top 5 Must-Haves |
|---------|------------------|
| Antiaging Pro | Clinically Proven, Retinol, Vitamin C, Peptides, SPF |
| Family/Mom | EWG Verified, Pregnancy Safe, Non-Toxic, Baby Safe, Affordable |
| Cancer/Sensitive | Oncologist Approved, Fragrance-Free, Hypoallergenic, Soothing, Pump |
| BIPOC/Inclusive | 40+ Shades, Vitamin C, Black-Owned, Buildable Coverage, SPF |
| Fluid | Cruelty-Free, LGBTQ+-Owned, Vegan, Refillable, Eco-Packaging |
| GenZ | Trending, Niacinamide, Cruelty-Free, Drugstore, Refillable |
