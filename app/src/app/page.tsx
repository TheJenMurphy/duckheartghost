import ProductCard, { type Product } from "@/components/ProductCard";

const products: Product[] = [
  {
    id: "westman-cleanser",
    name: "Vital Cleansing Foam",
    brand: "Westman Atelier",
    price: "$48",
    pricePerUnit: "$12.00/oz · Mid-range",
    category: "Cleanser",
    type: "Skincare",
    galleryImages: [
      "https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=400",
      "https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=400",
      "https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=400",
    ],
    voteData: { duck: 42, heart: 31, ghost: 27 },
    editorialTags: [
      { emoji: "🔥", label: "Hot", color: "#ff8c2a", bgColor: "rgba(255,140,42,.15)", borderColor: "rgba(255,140,42,.3)" },
      { emoji: "📱", label: "Viral", color: "#44ddee", bgColor: "rgba(68,221,238,.15)", borderColor: "rgba(68,221,238,.3)" },
      { emoji: "🐇", label: "Rabbit Hole", color: "#9955ff", bgColor: "rgba(153,85,255,.15)", borderColor: "rgba(153,85,255,.3)" },
    ],
    whatItDoes: [
      { label: "Hydrating", tooltip: "Increases water content in skin layers." },
      { label: "Brightening", tooltip: "Reduces dullness and evens skin tone." },
      { label: "Calming", tooltip: "Reduces visible redness and irritation." },
      { label: "Firming", tooltip: "Helps improve skin elasticity over time." },
      { label: "Pore-refining", tooltip: "Minimizes the appearance of enlarged pores." },
    ],
    whoItsFor: [
      { label: "All", tooltip: "Formulated to work across all skin types without irritation." },
      { label: "Sensitive", tooltip: "Tested and suitable for reactive or easily irritated skin." },
      { label: "Dry", tooltip: "Provides extra moisture for skin that lacks natural oils." },
    ],
    keyIngredients: [
      { label: "Niacinamide", tooltip: "Vitamin B3. Reduces pores, brightens, and improves skin barrier." },
      { label: "Hyaluronic Acid", tooltip: "Holds up to 1000x its weight in water. Deep hydration." },
      { label: "Ceramide NP", tooltip: "Lipid that seals the skin barrier and prevents moisture loss." },
    ],
    certifications: [
      { label: "EWG Score: 2", tooltip: "Rated low hazard (1–2) by the Environmental Working Group." },
      { label: "Clean at Sephora ✓", tooltip: "Free from 50+ ingredients Sephora considers harmful." },
      { label: "Leaping Bunny ✓", tooltip: "Certified cruelty-free. No animal testing at any stage." },
    ],
    metaBack: ["Skincare · Hair", "Synthetic · Botanical", "$48 · 4 fl oz"],
    verified: "Feb 2026",
  },
  {
    id: "dior-lip-oil",
    name: "Addict Lip Glow Oil",
    brand: "Dior",
    price: "$40",
    pricePerUnit: "$6.67/ml · Premium",
    category: "Lip Oil",
    type: "Makeup",
    galleryImages: [
      "https://images.unsplash.com/photo-1571781926291-c477ebfd024b?w=400",
      "https://images.unsplash.com/photo-1571781926291-c477ebfd024b?w=400",
      "https://images.unsplash.com/photo-1571781926291-c477ebfd024b?w=400",
    ],
    voteData: { duck: 55, heart: 28, ghost: 17 },
    editorialTags: [
      { emoji: "💎", label: "Luxe", color: "#9955ff", bgColor: "rgba(153,85,255,.15)", borderColor: "rgba(153,85,255,.3)" },
      { emoji: "📱", label: "Viral", color: "#44ddee", bgColor: "rgba(68,221,238,.15)", borderColor: "rgba(68,221,238,.3)" },
    ],
    whatItDoes: [
      { label: "Hydrating", tooltip: "Cherry oil delivers intense moisture to lips." },
      { label: "Color-enhancing", tooltip: "Reacts with lip chemistry for a custom shade." },
      { label: "Plumping", tooltip: "Creates a visibly fuller pout with glossy finish." },
      { label: "Smoothing", tooltip: "Fills fine lines on lips for a smooth surface." },
    ],
    whoItsFor: [
      { label: "All", tooltip: "Works for every skin tone and lip type." },
      { label: "Dry Lips", tooltip: "Specifically formulated to combat dry, flaky lips." },
      { label: "Sensitive", tooltip: "Fragrance-free and allergy tested." },
    ],
    keyIngredients: [
      { label: "Cherry Oil", tooltip: "Antioxidant-rich oil that softens and protects." },
      { label: "Jojoba Oil", tooltip: "Mimics skin's natural sebum for balanced moisture." },
      { label: "Squalane", tooltip: "Lightweight emollient that locks in hydration." },
    ],
    certifications: [
      { label: "Derm Tested ✓", tooltip: "Dermatologist tested for safety and efficacy." },
      { label: "Ophth. Approved ✓", tooltip: "Ophthalmologist approved. Safe near eyes." },
      { label: "Non-Comedogenic ✓", tooltip: "Won't clog pores or cause breakouts." },
    ],
    metaBack: ["Makeup · Lip", "Natural · Synthetic", "$40 · 6ml"],
    verified: "Feb 2026",
  },
  {
    id: "neutrogena-hydro",
    name: "Hydro Boost Water Gel",
    brand: "Neutrogena",
    price: "$19",
    pricePerUnit: "$0.40/g · Value",
    category: "Moisturizer",
    type: "Skincare",
    galleryImages: [
      "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400",
      "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400",
      "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400",
    ],
    voteData: { duck: 38, heart: 45, ghost: 17 },
    editorialTags: [
      { emoji: "🔥", label: "Hot", color: "#ff8c2a", bgColor: "rgba(255,140,42,.15)", borderColor: "rgba(255,140,42,.3)" },
      { emoji: "💰", label: "Best Value", color: "#00c4b0", bgColor: "rgba(0,196,176,.15)", borderColor: "rgba(0,196,176,.3)" },
    ],
    whatItDoes: [
      { label: "Hydrating", tooltip: "Hyaluronic acid attracts and holds moisture." },
      { label: "Oil-control", tooltip: "Lightweight gel absorbs without greasy residue." },
      { label: "Barrier repair", tooltip: "Strengthens natural skin barrier over time." },
      { label: "Soothing", tooltip: "Calms dry, tight, uncomfortable skin instantly." },
    ],
    whoItsFor: [
      { label: "Normal", tooltip: "Balanced skin that needs everyday hydration." },
      { label: "Dry", tooltip: "Quenches dehydrated skin with deep moisture." },
      { label: "Combination", tooltip: "Hydrates dry zones without overloading oily areas." },
      { label: "Sensitive", tooltip: "Fragrance-free and non-irritating formula." },
    ],
    keyIngredients: [
      { label: "Hyaluronic Acid", tooltip: "Holds 1000x its weight in water for deep hydration." },
      { label: "Glycerin", tooltip: "Humectant that draws moisture into the skin." },
      { label: "Dimethicone", tooltip: "Silicone that seals in moisture and smooths skin." },
    ],
    certifications: [
      { label: "Derm Recommended ✓", tooltip: "One of the most dermatologist-recommended brands." },
      { label: "Oil-Free ✓", tooltip: "Contains no oils. Ideal for acne-prone skin." },
      { label: "Non-Comedogenic ✓", tooltip: "Formulated to not clog pores." },
      { label: "Fragrance-Free ✓", tooltip: "No added fragrance. Reduces irritation risk." },
    ],
    metaBack: ["Skincare · Face", "Synthetic · Botanical", "$19 · 1.7 oz"],
    verified: "Feb 2026",
  },
];

export default function Home() {
  return (
    <div className="card-feed">
      {products.map((p) => (
        <div className="snap-item" key={p.id}>
          <ProductCard product={p} />
        </div>
      ))}
    </div>
  );
}
