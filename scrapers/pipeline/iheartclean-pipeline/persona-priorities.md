# Persona Priority Weights

Quick reference for scoring products by persona relevance.

## The 6 Personas

| Persona | Description | Key Priorities |
|---------|-------------|----------------|
| **Antiaging Pro** | Results-driven, 35-55+, invests in premium | Clinical proof, retinol, vitamin C, peptides, SPF |
| **Family/Mom** | Safety-first, pregnant/nursing/kids | EWG verified, pregnancy-safe, non-toxic, baby-safe |
| **Cancer/Sensitive** | Medical-grade needs, treatment side effects | Oncologist approved, fragrance-free, hypoallergenic, soothing |
| **BIPOC/Inclusive/Fluid** | Shade range, representation, gender-inclusive, ethics | 40+ shades, Black-owned, LGBTQ+-owned, cruelty-free |
| **GenZ** | Social-driven, budget-conscious, eco-focused | Trending, sustainable, drugstore, TikTok-approved |
| **Skeptic** | Distrusts marketing, wants proof | Third-party verified, science-backed, anti-greenwashing |

## Scoring Scale
- **1** = Critical (must-have, dealbreaker)
- **2** = High priority (strongly influences)

## Priority Lookup Table

```python
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
```

## Skeptic Persona Details

The Skeptic persona values **proof over promises**:

**Critical Attributes (Score 1):**
- Third-party certifications: EWG Verified, Leaping Bunny, B Corp, USDA Organic
- Clinical validation: Clinically proven, dermatologist tested/developed
- Medical credibility: Medical grade, allergy tested
- Transparency: Transparent sourcing

**What They Distrust:**
- Vague "clean" claims without certification
- "Natural" without organic certification
- Influencer/celebrity endorsements
- Trendy ingredients without research backing
- Greenwashing (sustainability claims without proof)

**What Converts Them:**
- Published clinical studies
- Third-party lab testing
- Ingredient transparency (full INCI lists)
- Certifications from recognized bodies
- Dermatologist/scientist endorsements (not influencers)
