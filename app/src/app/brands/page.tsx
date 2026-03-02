import BrandCard, { type Brand } from "@/components/BrandCard";

const brands: Brand[] = [
  {
    id: "tower-28",
    name: "Tower 28",
    tagline: "Clean beauty for sensitive skin",
    founded: "2019",
    location: "Los Angeles, CA",
    priceRange: "Accessible · $14–$30",
    galleryImages: [
      "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?w=400",
      "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400",
      "https://images.unsplash.com/photo-1487412947147-5cebf100ffc2?w=400",
    ],
    voteData: { duck: 8, heart: 82, ghost: 10 },
    description:
      "Founded by Amy Liu after her own eczema journey. Every product meets the National Eczema Association's ingredient standards. One of the few brands that is truly formulated for reactive skin — not just marketed that way.",
    values: [
      { label: "Sensitive-first", tooltip: "Every formula meets NEA standards for eczema-prone skin." },
      { label: "Transparent", tooltip: "Full ingredient lists, no hidden fragrance components." },
      { label: "Accessible pricing", tooltip: "Nothing over $30. Clean beauty shouldn't be luxury-only." },
      { label: "Joyful", tooltip: "Color cosmetics that are fun, not clinical." },
    ],
    ownership: [
      { label: "Woman-owned", tooltip: "Founded and led by Amy Liu." },
      { label: "AAPI-owned", tooltip: "Amy Liu is Asian-American." },
      { label: "Independent", tooltip: "Not owned by a conglomerate. Indie brand." },
    ],
    certifications: [
      { label: "NEA Accepted", tooltip: "National Eczema Association seal of acceptance." },
      { label: "Leaping Bunny", tooltip: "Certified cruelty-free at every stage." },
      { label: "Clean at Sephora", tooltip: "Meets Sephora's Clean beauty standards." },
      { label: "Vegan", tooltip: "No animal-derived ingredients in any product." },
    ],
    keyProducts: [
      { label: "BeachPlease Cream Blush", tooltip: "The hero. Buildable, dewy blush in a compact. $20." },
      { label: "SOS Daily Barrier Cream", tooltip: "Niacinamide + ceramides. Barrier repair. $34." },
      { label: "ShineOn Lip Jelly", tooltip: "Non-sticky, sheer color. $14. Cult favorite." },
      { label: "Milky Lip Jelly", tooltip: "Hydrating tinted lip balm. $16." },
    ],
    keyIngredients: [
      { label: "Niacinamide", tooltip: "Barrier repair and brightening. In multiple products." },
      { label: "Green Tea", tooltip: "Antioxidant protection. In their SOS line." },
      { label: "Aloe", tooltip: "Soothing base for sensitive formulas." },
    ],
    controversies: [
      "Shade range expansion requested by community — brand has acknowledged and is working on it.",
    ],
    verified: "Feb 2026",
  },
  {
    id: "ilia",
    name: "ILIA",
    tagline: "Clean beauty. Real results.",
    founded: "2011",
    location: "Laguna Beach, CA",
    priceRange: "Prestige · $26–$54",
    galleryImages: [
      "https://images.unsplash.com/photo-1571781926291-c477ebfd024b?w=400",
      "https://images.unsplash.com/photo-1512496015851-a90fb38ba796?w=400",
      "https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=400",
    ],
    voteData: { duck: 15, heart: 70, ghost: 15 },
    description:
      "One of the original clean beauty brands that proved you don't have to sacrifice performance. Their Super Serum Skin Tint changed the category. Squalane-based formulas that blur the line between skincare and makeup.",
    values: [
      { label: "Skin-first", tooltip: "Skincare ingredients in every color product." },
      { label: "Performance", tooltip: "Clean formulas that match conventional brand results." },
      { label: "Sustainability", tooltip: "B Corp certified. Packaging recycling program." },
      { label: "Inclusivity", tooltip: "Wide shade ranges across complexion products." },
    ],
    ownership: [
      { label: "Woman-founded", tooltip: "Founded by Sasha Plavsic." },
      { label: "Acquired", tooltip: "Acquired by Courtin-Clarins family (Clarins) in 2022." },
    ],
    certifications: [
      { label: "B Corp", tooltip: "Meets rigorous social and environmental performance standards." },
      { label: "EWG Verified", tooltip: "Products verified by Environmental Working Group." },
      { label: "Leaping Bunny", tooltip: "Certified cruelty-free." },
    ],
    keyProducts: [
      { label: "Super Serum Skin Tint", tooltip: "The product that made ILIA. Squalane-based, SPF 40. $48." },
      { label: "Limitless Lash Mascara", tooltip: "Clean mascara that actually performs. $28." },
      { label: "Multi-Stick", tooltip: "Cream color for cheeks, lips, and eyes. $34." },
      { label: "True Skin Serum Concealer", tooltip: "Squalane + vitamin C concealer. $30." },
    ],
    keyIngredients: [
      { label: "Squalane", tooltip: "Plant-derived emollient. Foundation of their formulas." },
      { label: "Niacinamide", tooltip: "Barrier support in complexion products." },
      { label: "Aloe", tooltip: "Soothing and hydrating base." },
    ],
    controversies: [
      "Clarins acquisition raised indie credibility concerns — formulas have remained unchanged so far.",
      "Some customers reported Skin Tint oxidation on certain skin types.",
    ],
    verified: "Feb 2026",
  },
  {
    id: "the-ordinary",
    name: "The Ordinary",
    tagline: "Clinical formulations with integrity",
    founded: "2016",
    location: "Toronto, Canada",
    priceRange: "Budget · $5–$15",
    galleryImages: [
      "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=400",
      "https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=400",
      "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400",
    ],
    voteData: { duck: 20, heart: 60, ghost: 20 },
    description:
      "Disrupted the entire skincare industry by making clinical-grade actives affordable. Stripped away marketing fluff and named products by their active ingredients. Now owned by Estee Lauder through DECIEM.",
    values: [
      { label: "Radical transparency", tooltip: "Products named by active ingredient and concentration." },
      { label: "Accessible pricing", tooltip: "Most products under $10. Democratized skincare." },
      { label: "Science-first", tooltip: "Formulations based on clinical research, not trends." },
      { label: "No marketing fluff", tooltip: "Minimal packaging, no aspirational branding." },
    ],
    ownership: [
      { label: "Corporate-owned", tooltip: "DECIEM acquired by Estee Lauder Companies in 2022." },
      { label: "Founded by Brandon Truaxe", tooltip: "Late founder who disrupted the beauty industry." },
    ],
    certifications: [
      { label: "Cruelty-free", tooltip: "No animal testing. Certified by PETA." },
      { label: "Vegan (most)", tooltip: "Majority of products are vegan. Some exceptions." },
    ],
    keyProducts: [
      { label: "Niacinamide 10% + Zinc 1%", tooltip: "The bestseller. Pore-refining serum. $6." },
      { label: "Hyaluronic Acid 2% + B5", tooltip: "Hydration serum. $8." },
      { label: "AHA 30% + BHA 2% Peeling Solution", tooltip: "The red mask. Viral exfoliant. $8." },
      { label: "Squalane Cleanser", tooltip: "Gentle oil cleanser. $8." },
    ],
    keyIngredients: [
      { label: "Niacinamide", tooltip: "Hero ingredient across multiple products." },
      { label: "Hyaluronic Acid", tooltip: "Core hydration ingredient." },
      { label: "Retinol", tooltip: "Multiple concentrations available: 0.2%, 0.5%, 1%." },
      { label: "Vitamin C", tooltip: "Multiple forms: L-ascorbic, ascorbyl glucoside, etc." },
    ],
    controversies: [
      "Estee Lauder acquisition changed perception from indie to corporate-backed.",
      "Founder Brandon Truaxe's public struggles and passing raised governance questions.",
      "Some products require significant skincare knowledge to use safely.",
    ],
    verified: "Feb 2026",
  },
];

export default function BrandsPage() {
  return (
    <div className="card-feed">
      {brands.map((b) => (
        <div className="snap-item" key={b.id}>
          <BrandCard brand={b} />
        </div>
      ))}
    </div>
  );
}
