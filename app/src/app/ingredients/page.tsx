import IngredientCard, { type Ingredient } from "@/components/IngredientCard";

const ingredients: Ingredient[] = [
  {
    id: "niacinamide",
    inci: "Niacinamide",
    aka: "Vitamin B3",
    type: "Synthetic",
    kind: "Skin Conditioning Agent",
    origin: "Derived from niacin (nicotinic acid)",
    galleryImages: [
      "https://images.unsplash.com/photo-1587854692152-cbe660dbde88?w=400",
      "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?w=400",
      "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?w=400",
    ],
    voteData: { duck: 12, heart: 78, ghost: 10 },
    description:
      "A form of Vitamin B3 that strengthens the skin barrier, reduces pore appearance, and evens skin tone. One of the most versatile and well-researched actives in skincare.",
    concentration: "2–10%",
    ph: "5.0–7.0",
    solubility: "Water-soluble",
    comedogenicRating: "0",
    ewgScore: "1",
    functions: [
      { label: "Barrier repair", tooltip: "Strengthens the lipid barrier to reduce transepidermal water loss." },
      { label: "Brightening", tooltip: "Inhibits melanosome transfer to reduce hyperpigmentation." },
      { label: "Oil control", tooltip: "Regulates sebum production without stripping the skin." },
      { label: "Anti-aging", tooltip: "Stimulates collagen synthesis and improves elasticity." },
      { label: "Pore-refining", tooltip: "Visibly reduces pore size with consistent use." },
    ],
    pairsWell: [
      { label: "Hyaluronic Acid", tooltip: "Complementary hydration — HA attracts water, niacinamide locks it in." },
      { label: "Zinc PCA", tooltip: "Synergistic oil control. Combined in many formulations." },
      { label: "Peptides", tooltip: "Both support barrier repair without competing for absorption." },
      { label: "Ceramides", tooltip: "Niacinamide boosts ceramide production — pairing amplifies the effect." },
    ],
    avoidWith: [
      { label: "Vitamin C (high %)", tooltip: "At high concentrations both compete for absorption. Stagger AM/PM or use combined formulas designed for stability." },
    ],
    foundIn: [
      { label: "The Ordinary Niacinamide 10%", tooltip: "10% niacinamide + 1% zinc. $6. Cult favorite." },
      { label: "Paula's Choice 10% Booster", tooltip: "Lightweight serum with panthenol. $46." },
      { label: "Tower 28 SOS Cream", tooltip: "Barrier recovery cream with niacinamide + ceramides. $34." },
    ],
    regStatus: [
      { region: "FDA", status: "permitted" },
      { region: "EU", status: "permitted" },
      { region: "Japan", status: "permitted" },
      { region: "Canada", status: "permitted" },
    ],
    sources: [
      { title: "Niacinamide mechanisms of action and topical use", journal: "J Cosmet Dermatol", year: 2020 },
      { title: "Topical niacinamide reduces yellowing and wrinkling", journal: "Br J Dermatol", year: 2002 },
    ],
    verified: "Feb 2026",
  },
  {
    id: "squalane",
    inci: "Squalane",
    aka: "Hydrogenated Squalene",
    type: "Botanical",
    kind: "Emollient",
    origin: "Derived from olives, sugarcane, or amaranth seed",
    galleryImages: [
      "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400",
      "https://images.unsplash.com/photo-1509281373149-e957c6296406?w=400",
      "https://images.unsplash.com/photo-1471943311424-646960669fbc?w=400",
    ],
    voteData: { duck: 18, heart: 68, ghost: 14 },
    description:
      "A stable, hydrogenated form of squalene — a lipid naturally produced by human skin. Lightweight, non-comedogenic, and compatible with virtually every skin type. Mimics the skin's own moisture barrier.",
    concentration: "1–100%",
    ph: "N/A (oil)",
    solubility: "Oil-soluble",
    comedogenicRating: "0",
    ewgScore: "1",
    functions: [
      { label: "Moisturizing", tooltip: "Prevents transepidermal water loss by forming a protective layer." },
      { label: "Barrier support", tooltip: "Replenishes lipids that mirror the skin's natural composition." },
      { label: "Anti-oxidant", tooltip: "Protects against oxidative damage from UV and pollution." },
      { label: "Softening", tooltip: "Instantly smooths rough, flaky, or dehydrated skin." },
    ],
    pairsWell: [
      { label: "Retinol", tooltip: "Squalane buffers retinol irritation while maintaining efficacy." },
      { label: "Vitamin C", tooltip: "Stabilizes L-ascorbic acid and prevents oxidation." },
      { label: "Hyaluronic Acid", tooltip: "HA pulls water in, squalane seals it — perfect layering partners." },
    ],
    avoidWith: [],
    foundIn: [
      { label: "Biossance Squalane Oil", tooltip: "100% sugarcane-derived squalane. $32. The benchmark." },
      { label: "The Ordinary Squalane", tooltip: "100% plant-derived. $8. No-frills, effective." },
      { label: "Ilia Super Serum Skin Tint", tooltip: "Squalane-based foundation. Skincare + coverage. $48." },
    ],
    regStatus: [
      { region: "FDA", status: "permitted" },
      { region: "EU", status: "permitted" },
      { region: "Japan", status: "permitted" },
      { region: "Canada", status: "permitted" },
    ],
    sources: [
      { title: "Squalane as a natural emollient", journal: "Int J Cosmet Sci", year: 2018 },
      { title: "Oxidative stability of squalane in topical formulations", journal: "J Am Oil Chem Soc", year: 2015 },
    ],
    verified: "Feb 2026",
  },
  {
    id: "salicylic-acid",
    inci: "Salicylic Acid",
    aka: "Beta Hydroxy Acid (BHA)",
    type: "Synthetic",
    kind: "Exfoliant",
    origin: "Originally from willow bark; now synthesized",
    galleryImages: [
      "https://images.unsplash.com/photo-1585435557343-3b0926e05c9c?w=400",
      "https://images.unsplash.com/photo-1457530378978-8bac673b8062?w=400",
      "https://images.unsplash.com/photo-1518531933037-91b2f5f229cc?w=400",
    ],
    voteData: { duck: 22, heart: 55, ghost: 23 },
    description:
      "The only oil-soluble BHA. Penetrates into pores to dissolve debris and excess sebum. The gold standard for acne-prone skin. Also has anti-inflammatory properties at lower concentrations.",
    concentration: "0.5–2%",
    ph: "3.0–4.0",
    solubility: "Oil-soluble",
    comedogenicRating: "0",
    ewgScore: "3",
    functions: [
      { label: "Exfoliating", tooltip: "Dissolves the bonds between dead cells for smoother turnover." },
      { label: "Pore-clearing", tooltip: "Oil-soluble — penetrates into pores to dissolve clogs." },
      { label: "Anti-inflammatory", tooltip: "Related to aspirin. Reduces redness and swelling." },
      { label: "Antibacterial", tooltip: "Creates an inhospitable pH for acne-causing bacteria." },
    ],
    pairsWell: [
      { label: "Niacinamide", tooltip: "Niacinamide soothes while BHA exfoliates. Great AM/PM split." },
      { label: "Clay", tooltip: "Clay absorbs oil on the surface, BHA clears it inside pores." },
      { label: "Centella Asiatica", tooltip: "Calming ingredient that offsets BHA's potential for dryness." },
    ],
    avoidWith: [
      { label: "AHAs (layered)", tooltip: "Using AHA and BHA simultaneously can over-exfoliate. Alternate days." },
      { label: "Retinol (same routine)", tooltip: "Both increase cell turnover. Layering risks irritation. Stagger usage." },
      { label: "Vitamin C (low pH)", tooltip: "Both are acidic. Combining can drop pH too low and cause stinging." },
    ],
    foundIn: [
      { label: "Paula's Choice 2% BHA Liquid", tooltip: "The cult classic. 2% salicylic acid. $34." },
      { label: "CosRx BHA Blackhead Power", tooltip: "4% betaine salicylate (gentler BHA). $25." },
      { label: "The Ordinary Salicylic Acid 2%", tooltip: "No-frills treatment solution. $6." },
    ],
    regStatus: [
      { region: "FDA", status: "permitted" },
      { region: "EU", status: "restricted" },
      { region: "Japan", status: "permitted" },
      { region: "Canada", status: "permitted" },
    ],
    sources: [
      { title: "Salicylic acid as a peeling agent", journal: "Clin Cosmet Investig Dermatol", year: 2015 },
      { title: "Comparative efficacy of BHA vs AHA in acne", journal: "J Clin Aesthet Dermatol", year: 2019 },
    ],
    verified: "Feb 2026",
  },
];

export default function IngredientsPage() {
  return (
    <div className="card-feed">
      {ingredients.map((ing) => (
        <div className="snap-item" key={ing.id}>
          <IngredientCard ingredient={ing} />
        </div>
      ))}
    </div>
  );
}
