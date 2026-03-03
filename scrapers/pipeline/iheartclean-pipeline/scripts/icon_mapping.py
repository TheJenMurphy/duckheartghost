#!/usr/bin/env python3
"""
Icon Mapping for iHeartClean Pipeline

Maps classifier-detected attributes to icon slugs.
Each icon represents a GROUP of related attributes.
If ANY attribute in the group is detected, that icon shows.

IMPORTANT: The slugs here MUST match the icon_config.py slugs exactly.
"""

# =============================================================================
# STARS ICONS (9 icons)
# Grid: 1-out-of-5, 2-out-of-5, 3-out-of-5, 4-out-of-5, 5-out-of-5,
#       trending, awards, professional, new-and-notable
# =============================================================================
STARS_MAPPING = {
    # Star ratings (positions 1-5)
    "1-out-of-5": ["1_out_of_5", "1_star", "one_star"],
    "2-out-of-5": ["2_out_of_5", "2_stars", "two_stars"],
    "3-out-of-5": ["3_out_of_5", "3_stars", "three_stars"],
    "4-out-of-5": ["4_out_of_5", "4_stars", "four_stars"],
    "5-out-of-5": ["5_out_of_5", "top_rated", "5_stars", "five_stars"],

    # Recognition icons (positions 6-9)
    "trending": ["trending", "best_seller", "customer_favorite", "viral", "cult_favorite"],
    "awards": ["awards", "editors_choice", "community_choice", "influencer_pick",
               "staff_pick", "readers_choice", "award_winning", "best_of_beauty"],
    "professional": ["professional", "expert_recommended"],
    "new-and-notable": ["new_and_notable", "new_arrival", "limited_edition", "exclusive",
                        "sold_out_before", "members_only", "pre_order"],
}

# =============================================================================
# SOURCE ICONS (8 icons)
# Grid: woman-owned, minority-owned, gender, professional,
#       medical-made, certifications, small-batch, country-of-origin
# =============================================================================
SOURCE_MAPPING = {
    "woman-owned": ["woman_owned", "female_founded", "women_led"],
    "minority-owned": ["minority_owned", "black_owned", "asian_owned",
                       "veteran_owned", "bipoc_owned", "aapi_owned", "latinx_owned"],
    "gender": ["gender", "lgbtq_owned", "lgbtqplus_owned", "queer_owned"],
    "professional": ["professional", "makeup_artist_made", "mua_founded",
                     "esthetician_formulated", "makeup_artist_brand"],
    "medical-made": ["medical_made", "dermatologist_developed", "medical_grade",
                     "pharmaceutical_grade", "therapeutic_grade"],
    "certifications": ["certifications", "b_corp", "b_corp_certified", "lab_verified",
                       "kosher", "kosher_certified", "halal", "halal_certified"],
    "small-batch": ["small_batch", "family_owned", "family_owned_facilities",
                    "indie_brand", "artisanal"],
    "country-of-origin": ["country_of_origin", "made_in_usa", "made_in_france",
                          "made_in_switzerland", "made_in_korea", "made_in_japan",
                          "made_in_china"],
}

# =============================================================================
# SAFETY ICONS (8 icons)
# Grid: pregnancy-safe, all-shades, all-ages, medical-approved,
#       tested, certifications, check, alert
# =============================================================================
SAFETY_MAPPING = {
    "pregnancy-safe": ["pregnancy_safe", "nursing_safe", "safe_for_pregnancy"],
    "all-shades": ["all_shades", "melanin_rich_safe", "melanin_rich"],
    "all-ages": ["all_ages", "baby_safe", "teen_safe", "teen_friendly", "all_ages_safe"],
    "medical-approved": ["medical_approved", "oncologist_approved", "post_surgery_safe",
                         "post_treatment_safe", "patient_friendly", "chemotherapy_safe",
                         "chemo_safe", "rosacea_friendly", "sensitive_conditions_friendly",
                         "menopause_safe", "eczema_safe", "pediatrician_approved"],
    "tested": ["tested", "allergy_tested", "dermatologist_tested", "family_tested",
               "ophthalmologist_tested", "survivor_tested", "dermatitis_tested",
               "independent_safety_testing", "independently_tested", "clinically_tested"],
    "certifications": ["gmp_certified", "whole_foods_premium", "nsf_certified",
                       "ewg_verified"],
    "check": ["check", "contact_lens_safe", "non_irritating", "patient_approved",
              "sensitive_skin_safe", "hypoallergenic", "safe_ingredients"],
    "alert": ["alert", "photosensitizing", "photo_sensitizing", "avoid_around_pets",
              "avoid_if_epileptic", "can_cause_irritation", "toxic", "safety_warning",
              "may_irritate"],
}

# =============================================================================
# SUPPORT ICONS (9 icons)
# Grid: moisturizing, oil-control, clarifying, nourishing,
#       antiaging, camera-ready, all-shades, time-saving, proven
# =============================================================================
SUPPORT_MAPPING = {
    "moisturizing": ["moisturizing", "hydrating", "occlusive", "moisture_rich"],
    "oil-control": ["oil_control", "non_comedogenic", "balancing", "mattifying",
                    "pore_minimizing"],
    "clarifying": ["clarifying", "exfoliating", "detoxifying", "anti_acne", "acne_fighting",
                   "pore_clearing", "deep_cleansing"],
    "nourishing": ["nourishing", "healing", "gentle", "calming", "stress_relieving",
                   "mood_lifting", "confidence_boosting", "energizing", "aromatherapy",
                   "breathable", "mineralizing", "soothing", "protecting", "sun_protecting",
                   "blue_light_protective"],
    "antiaging": ["antiaging", "anti_aging", "tightening", "firming", "smoothing",
                  "plumping", "lifting", "rejuvenating", "strengthening",
                  "wrinkle_reducing"],
    "camera-ready": ["camera_ready", "blurring", "perfecting", "blendable",
                     "transfer_resistant", "smudge_proof", "defining"],
    "all-shades": ["all_shades", "brightening", "concealing", "skin_tone_evening",
                   "layerable", "color_correcting", "hyperpigmentation_reducing",
                   "all_shades_supported", "fair_shades", "dark_shades", "melanin_rich",
                   "shade_range_40", "inclusive_shades", "all_skin_tones"],
    "time-saving": ["time_saving", "multi_functional", "long_wearing", "long_lasting",
                    "lightweight", "easy_application", "transfer_resistant", "quick_dry",
                    "multi_use", "easy_removal", "waterproof", "water_resistant",
                    "mistake_proof"],
    "proven": ["proven", "clinically_proven", "third_party_tested",
               "high_performance", "results_driven"],
}

# =============================================================================
# SUITABILITY ICONS (8 icons)
# Grid: all-shades, all-ages, gender, gentle,
#       skin-types, packaging, environment, appropriate
# =============================================================================
SUITABILITY_MAPPING = {
    "all-shades": ["all_shades", "melanin_rich", "dark_skin", "fair_skin",
                   "deep_skin_tones", "shade_range_40"],
    "all-ages": ["all_ages", "mature_skin", "aged_skin", "young_skin", "teen",
                 "youth", "aging_skin", "menopause"],
    "gender": ["gender", "gender_fluid", "trans", "men", "women", "all_gender",
               "unisex"],
    "gentle": ["gentle", "sensitive_skin", "hypoallergenic", "fragrance_free",
               "rosacea", "eczema"],
    "skin-types": ["skin_types", "normal_skin", "oily_skin", "acne_prone",
                   "dry_skin", "all_skin_types", "dehydrated_skin", "sensitive_skin",
                   "combination_skin", "universal"],
    "packaging": ["packaging", "travel_friendly", "sample_available", "mini",
                  "large_size", "value_size", "professional_size",
                  "makeup_artist_friendly", "esthetician_size", "travel_size"],
    "environment": ["environment", "active_safe", "workout_safe", "sport_safe",
                    "climate_resistant", "mask_friendly", "pollution_resistant",
                    "seasonal_adaptive", "hijab_friendly", "heat_resistant",
                    "sweat_resistant", "humidity_proof", "pool_safe", "beach_safe",
                    "climate_resilient", "active_sport_safe"],
    "appropriate": ["appropriate", "professional", "work_appropriate", "day_and_night",
                    "am_pm"],
}

# =============================================================================
# STRUCTURE ICONS (5 icons)
# Grid: format, formulation, how-where, performance, appearance
# =============================================================================
STRUCTURE_MAPPING = {
    "format": ["format", "minimalist_compatible", "travel_sized", "travel_size", "tube",
               "stick", "bottle", "compact", "jar", "pump", "dropper", "pencil",
               "roll_on", "palette", "k_beauty_cushion", "spray", "marker", "pen",
               "refill", "refillable_pkg", "airless_pump", "value_size"],
    "formulation": ["formulation", "liquid", "cream", "powder", "gel", "oil", "serum",
                    "balm", "lotion", "mousse", "whip", "butter", "milk", "foam",
                    "wax", "hybrid", "anhydrous", "micellar", "bi_phase", "encapsulated",
                    "mist"],
    "how-where": ["how_where", "instructions", "directions", "face", "cheek", "eye",
                  "lip", "tool", "tip", "trick", "best_practice", "lash", "brow",
                  "body", "hair", "mask", "treatment"],
    "performance": ["performance", "long_wearing", "waterproof", "transfer_resistant",
                    "smudge_proof", "quick_dry", "blendable", "layerable", "mistake_proof",
                    "multi_use", "multifunctional", "easy_application", "lightweight",
                    "breathable", "easy_removal", "water_resistant"],
    "appearance": ["appearance", "matte_finish", "matte", "dewy_finish", "dewy",
                   "natural_finish", "satin_finish", "satin", "glossy_finish", "glossy",
                   "radiant_finish", "radiant", "luminous_finish", "luminous",
                   "buildable_coverage", "buildable", "sheer_coverage", "light_coverage",
                   "medium_coverage", "full_coverage"],
}

# =============================================================================
# SUBSTANCE ICONS (4 icons)
# Grid: key-ingredients, base-ingredients, free-from, transparency
# =============================================================================
SUBSTANCE_MAPPING = {
    "key-ingredients": ["key_ingredients", "actives", "vitamin_c", "with_vitamin_c",
                        "hyaluronic_acid", "with_hyaluronic_acid", "niacinamide",
                        "with_niacinamide", "retinol", "with_retinol", "bakuchiol",
                        "with_bakuchiol", "peptides", "with_peptides", "ceramides",
                        "with_ceramides", "cbd", "with_cbd", "probiotics", "with_probiotics",
                        "antioxidants", "with_antioxidants", "adaptogens", "with_adaptogens",
                        "squalane", "centella", "aloe", "collagen", "caffeine", "aha_bha",
                        "spf", "zinc_oxide"],
    "base-ingredients": ["base_ingredients", "food_based", "mineral_based", "plant_based",
                         "plant_derived_synthetic", "synthetic", "vitamin", "vitamin_based",
                         "petroleum", "mineral_oil_based", "fermented", "water_based",
                         "oil_based"],
    "free-from": ["free_from", "free", "free_of", "fragrance_free", "scent_free",
                  "paraben_free", "sulfate_free", "phthalate_free", "alcohol_free",
                  "silicone_free", "mineral_oil_free", "synthetic_dye_free", "talc_free",
                  "formaldehyde_free", "gluten_free", "petroleum_free", "peg_free",
                  "nano_free", "pfas_free", "heavy_metal_free", "coal_tar_free",
                  "dairy_free", "nut_free", "soy_free", "corn_free", "mushroom_free",
                  "shellfish_free", "palm_oil_free", "no_synthetic_fragrance"],
    "transparency": ["transparency", "transparent", "full_disclosure", "transparent_sourcing",
                     "full_ingredient_list", "inci_list"],
}

# =============================================================================
# SUSTAINABILITY ICONS (8 icons)
# Grid: organic, vegan, cruelty-free, environment,
#       manufacturing, donation, ingredients, packaging
# =============================================================================
SUSTAINABILITY_MAPPING = {
    "organic": ["organic", "usda_organic", "cosmos_certified_organic", "cosmos_organic",
                "certified_organic"],
    "vegan": ["vegan", "plant_based", "no_animal_ingredients"],
    "cruelty-free": ["cruelty_free", "peta_approved", "peta_certified",
                     "leaping_bunny", "leaping_bunny_certified", "not_tested_on_animals"],
    "environment": ["environment", "reef_safe", "ocean_positive", "water_conservation",
                    "carbon_neutral", "climate_neutral_certified", "climate_neutral",
                    "fsc_certified", "pefc_certified", "blue_angel", "nordic_swan",
                    "ocean_safe", "water_conscious", "waterless", "renewable_energy",
                    "low_carbon"],
    "manufacturing": ["manufacturing", "pure_processing", "renewable_energy_made",
                      "local_production", "local_regional_production", "cradle_to_cradle",
                      "zero_waste_manufacturing", "b_corp_certified", "b_corp"],
    "donation": ["donation", "one_percent_planet", "1_percent_for_the_planet",
                 "charitable", "giving_back"],
    "ingredients": ["ingredients", "fair_trade", "upcycled_ingredients",
                    "sustainable_agriculture", "wildcrafted", "ethically_sourced",
                    "microplastic_free", "community_trade", "locally_sourced_materials",
                    "ewg_verified", "solid_format", "waterless_formulas",
                    "sustainably_sourced"],
    "packaging": ["packaging", "recyclable", "recycled", "recycled_content", "plastic_free",
                  "compostable_packaging", "refillable", "fsc_certified_packaging",
                  "fsc_certified", "biodegradable", "zero_waste", "minimal_packaging",
                  "plant_based_packaging", "bio_plastic", "ocean_plastic", "upcycled_materials",
                  "glass", "aluminum", "bamboo", "cork", "mushroom_packaging", "seaweed_based",
                  "reusable", "mono_material", "no_secondary_packaging", "no_outer_packaging",
                  "right_sized", "lightweight_packaging", "modular", "stackable", "dissolvable",
                  "naked", "package_free", "seed_paper", "take_back_program",
                  "terracycle_partnership", "deposit_return", "closed_loop_recycling",
                  "how2recycle_label", "local_recycling_compatible", "carbon_neutral_packaging",
                  "locally_sourced_materials", "water_based_inks", "no_virgin_plastic",
                  "usda_biopreferred", "ok_compost", "tuv_home_compost", "dropper_bottles",
                  "refill_pouches", "magnetic_refill_pans", "aluminum_tubes", "pcr_plastic",
                  "ocean_bound_plastic", "sugarcane_plastic", "reef_safe_sunscreen_packaging",
                  "eco_packaging", "compostable"],
}

# =============================================================================
# SPEND ICONS (9 icons)
# Grid: budget, accessible, prestige, luxury,
#       subscribe, value-set, sale, dupe-discovery, returns
# =============================================================================
SPEND_MAPPING = {
    "budget": ["budget", "under_20", "drugstore"],
    "accessible": ["accessible", "20_to_49", "moderate_price"],
    "prestige": ["prestige", "50_to_99", "premium"],
    "luxury": ["luxury", "100_and_over", "over_100", "over_150", "ultra_premium"],
    "subscribe": ["subscribe", "subscribe_and_save", "subscription", "auto_replenish",
                  "auto_delivery", "auto_ship", "auto_refill", "replenishment",
                  "recurring_order", "scheduled_delivery", "standing_order", "membership",
                  "beauty_box", "sample_box", "discovery_box", "mystery_box", "curated_box",
                  "monthly_box", "quarterly_box", "clean_beauty_box", "indie_box",
                  "mens_box", "self_care_box"],
    "value-set": ["value_set", "family_sized", "value_sized", "bundle", "travel_sized",
                  "travel_size", "sample_sized", "sample_available", "best_value",
                  "bulk_savings", "multi_buy_discount", "multi_buy", "discovery_kit",
                  "set", "kit", "duo", "mini", "deluxe_sample", "miniature", "on_the_go",
                  "jet_set", "weekender", "carry_on", "pocket_size", "purse_size",
                  "trial_size", "tester", "try_me_size", "sampler", "explorer_set",
                  "introduction_set", "coffret", "pochette", "gwp", "gift_with_purchase",
                  "bonus", "freebie", "sachet", "packet", "pod", "bogo", "gift_set",
                  "starter_kit"],
    "sale": ["sale", "on_sale", "discount", "discounted", "sale_price"],
    "dupe-discovery": ["dupe_discovery", "dupe", "duplicate", "similar_product",
                       "similar_find", "affordable_alternative", "budget_dupe"],
    "returns": ["returns", "30_day_guarantee", "60_day_guarantee", "guarantee",
                "money_back", "money_back_guarantee", "free_returns", "easy_returns"],
}


def get_icon_slugs_for_category(detected_attrs: list, mapping: dict) -> list:
    """
    Given a list of detected attributes and a category mapping,
    return the list of icon slugs that should show.
    """
    icon_slugs = []
    detected_set = set(a.lower().replace("-", "_") for a in detected_attrs)

    for icon_slug, trigger_attrs in mapping.items():
        trigger_set = set(a.lower() for a in trigger_attrs)
        if detected_set & trigger_set:  # If any overlap
            icon_slugs.append(icon_slug)

    return icon_slugs


def map_attributes_to_icons(classified_product: dict) -> dict:
    """
    Takes a classified product and returns icon slugs for each 9S category.

    Input: classified product with detected_attributes list
    Output: dict with icon slugs for each 9S category
    """
    detected = classified_product.get("detected_attributes", [])

    return {
        "stars": get_icon_slugs_for_category(detected, STARS_MAPPING),
        "source": get_icon_slugs_for_category(detected, SOURCE_MAPPING),
        "safety": get_icon_slugs_for_category(detected, SAFETY_MAPPING),
        "support": get_icon_slugs_for_category(detected, SUPPORT_MAPPING),
        "suitability": get_icon_slugs_for_category(detected, SUITABILITY_MAPPING),
        "structure": get_icon_slugs_for_category(detected, STRUCTURE_MAPPING),
        "substance": get_icon_slugs_for_category(detected, SUBSTANCE_MAPPING),
        "sustainability": get_icon_slugs_for_category(detected, SUSTAINABILITY_MAPPING),
        "spend": get_icon_slugs_for_category(detected, SPEND_MAPPING),
    }


def format_for_webflow(icon_slugs: list) -> str:
    """
    Format icon slugs as comma-separated string for Webflow data attribute.
    """
    return ", ".join(icon_slugs) if icon_slugs else ""


if __name__ == "__main__":
    # Test with sample attributes
    test_attrs = [
        "vegan", "cruelty_free", "hydrating", "clinically_proven",
        "sensitive_skin", "pregnancy_safe", "vitamin_c", "serum",
        "travel_size", "prestige", "dermatologist_tested", "best_seller",
        "clarifying", "exfoliating"
    ]

    test_product = {"detected_attributes": test_attrs}
    icons = map_attributes_to_icons(test_product)

    print("Test attributes:", test_attrs)
    print("\nMapped icons:")
    for cat, slugs in icons.items():
        if slugs:
            print(f"  {cat}: {format_for_webflow(slugs)}")
