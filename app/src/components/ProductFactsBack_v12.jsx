import { useState, useRef } from "react";

const COLORS = {
  isItSafe:     "#e9455c",
  whatItDoes:   "#ff6eb0",
  whoItsFor:    "#9955ff",
  whatItIs:     "#3f8def",
  whatsTheDeal: "#00c4b0",
  ingredients:  "#44ddee",
  packaging:    "#3f8def",
  rabbitHole:   "#ff8c2a",
  white:        "#ffffff",
  grey:         "#888888",
  divider:      "rgba(255,255,255,.15)",
  bg:           "#000000",
};

const SECTIONS = [
  { key: "safe",  label: "IS IT SAFE?",      color: COLORS.isItSafe     },
  { key: "does",  label: "WHAT DOES IT DO?",  color: COLORS.whatItDoes   },
  { key: "for",   label: "WHO'S IT FOR?",     color: COLORS.whoItsFor    },
  { key: "is",    label: "WHAT IS IT?",       color: COLORS.whatItIs     },
  { key: "deal",  label: "WHAT'S THE DEAL?", color: COLORS.whatsTheDeal },
];

const sampleProduct = {
  name: "BeachPlease Cream Blush",
  brand: "Tower 28",
  brandSlug: "tower-28",
  price: "$20",
  pricePerOz: "$142.86/oz",
  priceTier: "Accessible",
  size: "0.14 oz",
  category: "Cheek",
  type: "Blush",
  formulation: "Cream",
  packaging: "Compact",
  verified: "Mar 2026",
  sections: {
    safe: {
      ewgScore: "1",
      ewgLabel: "Low Hazard",
      certifications: [
        { label: "EWG Verified",         tooltip: "Meets EWG's strictest standards for ingredient safety" },
        { label: "Dermatologist Tested", tooltip: "Clinically tested by board-certified dermatologists" },
        { label: "Fragrance Free",       tooltip: "Contains no added fragrance or parfum" },
      ],
      regulations: [
        { label: "EU Compliant",         tooltip: "Meets EU cosmetic safety regulations (1,600+ banned ingredients)" },
        { label: "California Safe",      tooltip: "Complies with California Toxic-Free Cosmetics Act" },
      ],
    },
    does: {
      benefits: [
        { label: "Buildable Color", tooltip: "Sheer to medium coverage depending on how much you layer" },
        { label: "Natural Flush",   tooltip: "Mimics the look of naturally flushed skin" },
        { label: "Hydrating",       tooltip: "Jojoba oil keeps skin moisturized throughout the day" },
        { label: "Long-wearing",    tooltip: "Up to 8 hours wear time in clinical testing" },
        { label: "Non-comedogenic", tooltip: "Won't clog pores — tested and confirmed" },
      ],
      finish: [
        { label: "Satin",     tooltip: "Neither matte nor dewy — a soft natural finish" },
        { label: "Buildable", tooltip: "Layer for more intensity" },
      ],
      coverage: [
        { label: "Sheer",  tooltip: "Light wash of color, very natural" },
        { label: "Medium", tooltip: "Build up to medium coverage with additional layers" },
      ],
    },
    for: {
      skinTypes: [
        { label: "Dry",       tooltip: "Cream formula is especially flattering on dry skin" },
        { label: "Normal",    tooltip: "Works well with normal skin types" },
        { label: "Sensitive", tooltip: "Free of known irritants, suitable for sensitive skin" },
      ],
      skinConcerns: [
        { label: "Dullness",    tooltip: "Adds a flush of color that brightens the complexion" },
        { label: "Dryness",     tooltip: "Jojoba oil provides lasting moisture" },
        { label: "Uneven Tone", tooltip: "Buildable color evens out and enhances skin tone" },
      ],
      personas: [
        { label: "Clean Curious", tooltip: "Great entry point for people new to clean beauty" },
        { label: "Minimalist",    tooltip: "Does double duty as blush + lip color" },
      ],
      notFor: [
        { label: "Oily Skin", tooltip: "Cream formulas may not last as long — set with powder" },
      ],
    },
    is: {
      keyIngredients: [
        { label: "Castor Seed Oil",              slug: "castor-seed-oil",              tooltip: "Ricinus Communis Seed Oil — Emollient base. Gives the formula its glide." },
        { label: "Jojoba Oil",                   slug: "jojoba-oil",                   tooltip: "Simmondsia Chinensis Seed Oil — Wax ester that mimics skin's own sebum." },
        { label: "Caprylic/Capric Triglyceride", slug: "caprylic-capric-triglyceride", tooltip: "Lightweight emollient from coconut oil. Helps spread formula evenly." },
      ],
      allIngredients: [
        { label: "Ricinus Communis Seed Oil",     slug: "castor-seed-oil" },
        { label: "Caprylic/Capric Triglyceride",  slug: "caprylic-capric-triglyceride" },
        { label: "Mica",                          slug: "mica" },
        { label: "Silica",                        slug: "silica" },
        { label: "Synthetic Beeswax",             slug: "synthetic-beeswax" },
        { label: "Simmondsia Chinensis Seed Oil", slug: "jojoba-oil" },
        { label: "Titanium Dioxide (CI 77891)",   slug: "titanium-dioxide" },
        { label: "Iron Oxides (CI 77491)",        slug: "iron-oxides" },
        { label: "Red 7 Lake (CI 15850)",         slug: "red-7-lake" },
      ],
      formulaBase: [
        { label: "Oil-based",   tooltip: "Lipophilic base — won't oxidize or change color on skin" },
        { label: "Anhydrous",   tooltip: "No water in the formula — no preservatives needed" },
      ],
      packaging: [
        { label: "Compact",     tooltip: "Small plastic compact with built-in mirror" },
        { label: "Travel-size", tooltip: "0.14oz qualifies as TSA carry-on friendly" },
        { label: "Plastic",     tooltip: "Outer case is plastic — not currently refillable" },
      ],
    },
    deal: {
      price: "$20",
      pricePerOz: "$142.86/oz",
      priceTier: "Accessible",
      retailers: [
        { label: "Credo Beauty",    url: "https://www.credobeauty.com/?awinmid=XXXXX&awinaffid=XXXXX", active: true  },
        { label: "Tower 28 Direct", url: "",                                                             active: false },
        { label: "Sephora",         url: "",                                                             active: false },
      ],
      affiliateNote: "DHG earns a small commission when you shop these links — disclosed because that's the whole point.",
    },
  },
};

/* ── PILL ── */
function Pill({ label, color, tooltip }) {
  const [showTip, setShowTip] = useState(false);
  const [tipBelow, setTipBelow] = useState(false);
  const pillRef = useRef(null);
  const tipRef = useRef(null);

  const handleMouseEnter = () => {
    // Check if pill is in top half of screen — if so, show tooltip below
    if (pillRef.current) {
      const rect = pillRef.current.getBoundingClientRect();
      setTipBelow(rect.top < window.innerHeight / 2);
    }
    setShowTip(true);
    requestAnimationFrame(() => {
      if (!tipRef.current || !pillRef.current) return;
      const tip = tipRef.current.getBoundingClientRect();
      const vw = window.innerWidth;
      if (tip.right > vw - 12) {
        tipRef.current.style.left = "auto";
        tipRef.current.style.right = "0";
      } else {
        tipRef.current.style.left = "0";
        tipRef.current.style.right = "auto";
      }
    });
  };

  return (
    <div ref={pillRef} style={{ position: "relative", display: "inline-block" }}>
      <span
        onMouseEnter={handleMouseEnter}
        onMouseLeave={() => setShowTip(false)}
        style={{
          display: "inline-block",
          padding: "5px 12px",
          borderRadius: 9999,
          fontSize: ".88rem",
          fontFamily: "'Outfit', sans-serif",
          fontWeight: 600,
          color: color,
          background: "transparent",
          border: `1px solid ${color}30`,
          whiteSpace: "nowrap",
          cursor: "default",
        }}
      >
        {label}
      </span>
      {showTip && tooltip && (
        <div
          ref={tipRef}
          style={{
            position: "absolute",
            ...(tipBelow
              ? { top: "calc(100% + 8px)" }
              : { bottom: "calc(100% + 8px)" }),
            left: 0,
            zIndex: 9999,
            background: "rgba(18,18,20,.97)",
            backdropFilter: "blur(16px)",
            border: `1px solid ${color}40`,
            borderRadius: 12,
            padding: "10px 14px",
            width: 220,
            pointerEvents: "none",
            boxShadow: "0 4px 24px rgba(0,0,0,.6)",
          }}
        >
          <div style={{ fontSize: ".82rem", color: "rgba(255,255,255,.9)", fontFamily: "'Outfit', sans-serif", lineHeight: 1.5 }}>
            {tooltip}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── SUB-LABEL ── */
function SubLabel({ text }) {
  return (
    <div style={{
      fontSize: ".72rem",
      fontFamily: "'Space Mono', monospace",
      color: "rgba(255,255,255,.5)",
      textTransform: "uppercase",
      letterSpacing: ".06em",
      marginBottom: 7,
    }}>
      {text}
    </div>
  );
}

/* ── SECTION CONTENT ── */
function SectionContent({ sectionKey, data }) {

  if (sectionKey === "safe") return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontFamily: "'Space Mono', monospace", fontSize: "1rem", fontWeight: 700, color: COLORS.isItSafe }}>EWG {data.ewgScore}</span>
        <span style={{ fontFamily: "'Space Mono', monospace", fontSize: ".78rem", color: "rgba(255,255,255,.5)", textTransform: "uppercase", letterSpacing: ".05em" }}>{data.ewgLabel}</span>
      </div>
      <div>
        <SubLabel text="Certifications" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {data.certifications.map((c, i) => <Pill key={i} label={c.label} color={COLORS.isItSafe} tooltip={c.tooltip} />)}
        </div>
      </div>
      <div>
        <SubLabel text="Regulatory" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {data.regulations.map((r, i) => <Pill key={i} label={r.label} color={COLORS.isItSafe} tooltip={r.tooltip} />)}
        </div>
      </div>
    </div>
  );

  if (sectionKey === "does") return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div>
        <SubLabel text="Benefits" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {data.benefits.map((b, i) => <Pill key={i} label={b.label} color={COLORS.whatItDoes} tooltip={b.tooltip} />)}
        </div>
      </div>
      <div>
        <SubLabel text="Finish" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {data.finish.map((f, i) => <Pill key={i} label={f.label} color={COLORS.whatItDoes} tooltip={f.tooltip} />)}
        </div>
      </div>
      <div>
        <SubLabel text="Coverage" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {data.coverage.map((c, i) => <Pill key={i} label={c.label} color={COLORS.whatItDoes} tooltip={c.tooltip} />)}
        </div>
      </div>
    </div>
  );

  if (sectionKey === "for") return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div>
        <SubLabel text="Skin Type" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {data.skinTypes.map((s, i) => <Pill key={i} label={s.label} color={COLORS.whoItsFor} tooltip={s.tooltip} />)}
        </div>
      </div>
      <div>
        <SubLabel text="Skin Concerns" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {data.skinConcerns.map((s, i) => <Pill key={i} label={s.label} color={COLORS.whoItsFor} tooltip={s.tooltip} />)}
        </div>
      </div>
      <div>
        <SubLabel text="Best For" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {data.personas.map((p, i) => <Pill key={i} label={p.label} color={COLORS.whoItsFor} tooltip={p.tooltip} />)}
        </div>
      </div>
      {data.notFor.length > 0 && (
        <div>
          <SubLabel text="Not Ideal For" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {data.notFor.map((n, i) => <Pill key={i} label={n.label} color={COLORS.grey} tooltip={n.tooltip} />)}
          </div>
        </div>
      )}
    </div>
  );

  if (sectionKey === "is") {
    const [showAll, setShowAll] = useState(false);
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div>
          <SubLabel text="Key Ingredients" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {data.keyIngredients.map((ing, i) => <Pill key={i} label={ing.label} color={COLORS.ingredients} tooltip={ing.tooltip} />)}
          </div>
          <div onClick={() => setShowAll(!showAll)} style={{ marginTop: 10, fontSize: ".88rem", fontWeight: 700, color: COLORS.rabbitHole, cursor: "pointer", display: "inline-block" }}>
            {showAll ? "Hide ingredients ↑" : "See all ingredients →"}
          </div>
          {showAll && (
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 5, paddingLeft: 4, borderLeft: `2px solid ${COLORS.ingredients}40` }}>
              {data.allIngredients.map((ing, i) => (
                <a key={i} href={`/ingredients/${ing.slug}`} style={{ fontSize: ".85rem", fontFamily: "'Outfit', sans-serif", color: COLORS.ingredients, textDecoration: "none", padding: "2px 0 2px 10px", display: "block" }}>
                  {ing.label} →
                </a>
              ))}
            </div>
          )}
        </div>
        <div>
          <SubLabel text="Formula Base" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {data.formulaBase.map((f, i) => <Pill key={i} label={f.label} color={COLORS.packaging} tooltip={f.tooltip} />)}
          </div>
        </div>
        <div>
          <SubLabel text="Packaging" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {data.packaging.map((p, i) => <Pill key={i} label={p.label} color={COLORS.packaging} tooltip={p.tooltip} />)}
          </div>
        </div>
      </div>
    );
  }

  if (sectionKey === "deal") return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center" }}>
        <div style={{ flex: 1, textAlign: "left" }}>
          <span style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 900, fontSize: "1.5rem", color: "rgba(255,255,255,.85)" }}>{data.price}</span>
        </div>
        <div style={{ flex: 1, textAlign: "center" }}>
          <span style={{ fontFamily: "'Outfit', sans-serif", fontSize: ".88rem", color: "rgba(255,255,255,.5)" }}>{data.pricePerOz}</span>
        </div>
        <div style={{ flex: 1, textAlign: "right" }}>
          <span style={{ fontFamily: "'Space Mono', monospace", fontSize: ".72rem", color: "rgba(255,255,255,.4)", textTransform: "uppercase" }}>{data.priceTier}</span>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {data.retailers.map((r, i) => r.active ? (
          <a key={i} href={r.url} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "2px", borderRadius: 10, background: "linear-gradient(90deg,#ffaa00,#ff8c2a,#ff5533,#ff4466,#ff6eb0,#d946ef,#9955ff,#3399ff,#44ddee,#00c4b0)", textDecoration: "none" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", padding: "9px 14px", borderRadius: 8, background: "#000" }}>
              <span style={{ fontFamily: "'Outfit', sans-serif", fontSize: ".9rem", fontWeight: 700, color: COLORS.whatsTheDeal }}>👜 {r.label}</span>
              <span style={{ fontSize: 13, color: COLORS.whatsTheDeal }}>→</span>
            </div>
          </a>
        ) : (
          <div key={i} style={{ display: "flex", alignItems: "center", padding: "9px 14px", borderRadius: 8, border: "1px solid rgba(255,255,255,.12)" }}>
            <span style={{ fontFamily: "'Outfit', sans-serif", fontSize: ".9rem", fontWeight: 600, color: "rgba(255,255,255,.25)" }}>{r.label}</span>
          </div>
        ))}
      </div>
      <div style={{ fontSize: ".72rem", fontFamily: "'Space Mono', monospace", color: "rgba(255,255,255,.4)", lineHeight: 1.6, paddingTop: 8, borderTop: "1px solid rgba(255,255,255,.15)" }}>
        {data.affiliateNote}
      </div>
    </div>
  );

  return null;
}

/* ── SECTION WRAPPER ── */
function Section({ section, data, isOpen, onToggle }) {
  return (
    <div style={{ borderTop: "1px solid rgba(255,255,255,.15)" }}>
      <button onClick={onToggle} style={{ width: "100%", padding: "11px 16px", background: "transparent", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 8, transition: "background 0.2s" }}>
        <span style={{ fontSize: ".9rem", fontFamily: "'Outfit', sans-serif", fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: isOpen ? section.color : "rgba(255,255,255,.7)", flex: 1, textAlign: "left", transition: "color 0.2s" }}>
          {section.label}
        </span>
        <span style={{ fontSize: 14, color: isOpen ? section.color : "rgba(255,255,255,.5)", transform: isOpen ? "rotate(90deg)" : "none", transition: "transform 0.2s, color 0.2s", display: "inline-block", lineHeight: 1 }}>
          &#9654;
        </span>
      </button>
      <div style={{ maxHeight: isOpen ? 700 : 0, overflow: "hidden", transition: "max-height 0.35s ease" }}>
        <div style={{ padding: "2px 16px 16px" }}>
          <SectionContent sectionKey={section.key} data={data} />
        </div>
      </div>
    </div>
  );
}

/* ── MAIN ── */
export default function ProductFactsBack({ product = sampleProduct, onFlipBack }) {
  const [openSection, setOpenSection] = useState("safe");
  const toggleSection = (key) => setOpenSection(openSection === key ? null : key);

  return (
    <div style={{ width: "100%", maxWidth: 380, background: COLORS.bg, color: COLORS.white, fontFamily: "'Outfit', sans-serif" }}>

      <div style={{ padding: "12px 16px 10px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: "2rem", fontWeight: 900, color: COLORS.white, letterSpacing: "-.02em", lineHeight: 1, marginBottom: 6 }}>
              Product Facts
            </div>
            <div style={{ height: 2, background: "#ffffff", marginBottom: 10 }} />
            <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "rgba(255,255,255,.6)", lineHeight: 1.2 }}>
              {product.name}
            </div>
            <a href={`/brands/${product.brandSlug}`} style={{ fontSize: "1rem", fontWeight: 700, color: COLORS.rabbitHole, textDecoration: "none", display: "inline-block", marginTop: 4 }}>
              {product.brand} →
            </a>
          </div>
          <button onClick={onFlipBack} style={{ width: 34, height: 34, borderRadius: "50%", background: "rgba(255,255,255,.06)", border: "1px solid rgba(255,255,255,.15)", color: "rgba(255,255,255,.6)", fontSize: 15, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            ↺
          </button>
        </div>
        <div style={{ fontSize: ".85rem", color: "rgba(255,255,255,.55)", marginTop: 10, letterSpacing: ".01em", lineHeight: 1.8 }}>
          {product.category} · {product.type} · {product.formulation} · {product.packaging} · {product.size}
        </div>
      </div>

      <div style={{ height: 1, background: "rgba(255,255,255,.2)", margin: "0 16px" }} />

      <div>
        {SECTIONS.map((section) => (
          <Section key={section.key} section={section} data={product.sections[section.key]} isOpen={openSection === section.key} onToggle={() => toggleSection(section.key)} />
        ))}
      </div>

      <div style={{ textAlign: "center", padding: "10px 16px 14px", borderTop: "1px solid rgba(255,255,255,.15)", marginTop: 4 }}>
        <span style={{ fontFamily: "'Space Mono', monospace", fontSize: ".72rem", color: "rgba(255,255,255,.5)", letterSpacing: ".06em", textTransform: "uppercase" }}>
          Verified {product.verified}
        </span>
      </div>

    </div>
  );
}
