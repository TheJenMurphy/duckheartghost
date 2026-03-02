import { useState } from "react";

/* ─────────────────────────────────────────
   DUCK HEART GHOST · Product Facts Back
   Final Color System · March 2026
───────────────────────────────────────── */

const COLORS = {
  // Five Sections
  isItSafe:       "#e9455c",   // Safety red    — IS IT SAFE?
  whatItDoes:     "#ff4d8a",   // Pink          — WHAT IT DOES
  whoItsFor:      "#9955ff",   // Purple        — WHO IT'S FOR
  whatItIs:       "#3f8def",   // Blue          — WHAT IT IS (header)
  whatsTheDeal:   "#00c4b0",   // Clutch teal   — WHAT'S THE DEAL?

  // Pills inside WHAT IT IS
  ingredients:    "#44ddee",   // Aqua  — ingredient pills (rabbit hole links)
  packaging:      "#3f8def",   // Blue  — packaging / formula pills

  // Navigation — ALL links out to other cards/pages
  rabbitHole:     "#ff8c2a",

  // Neutrals
  white:          "#ffffff",
  grey:           "#777777",
  divider:        "rgba(255,255,255,.12)",
  bg:             "#000000",
};

/* ─────────────────────────────────────────
   FIVE SECTIONS — ordered Safety → Deal
   Color progression: red → pink → purple → blue → teal
───────────────────────────────────────── */
const SECTIONS = [
  { key: "safe",  label: "IS IT SAFE?",      color: COLORS.isItSafe,     icon: "🛡️" },
  { key: "does",  label: "WHAT IT DOES",      color: COLORS.whatItDoes,   icon: "✨" },
  { key: "for",   label: "WHO IT'S FOR",      color: COLORS.whoItsFor,    icon: "🎯" },
  { key: "is",    label: "WHAT IT IS",        color: COLORS.whatItIs,     icon: "🔬" },
  { key: "deal",  label: "WHAT'S THE DEAL?",  color: COLORS.whatsTheDeal, icon: "💰" },
];

/* ─────────────────────────────────────────
   SAMPLE PRODUCT DATA
───────────────────────────────────────── */
const sampleProduct = {
  name: "BeachPlease Cream Blush",
  brand: "Tower 28",
  brandSlug: "tower-28",
  price: "$20",
  pricePerOz: "$142.86/oz",
  priceTier: "Accessible",
  size: "0.14 oz",
  category: "Blush",
  type: "Cream",
  verified: "Mar 2026",

  sections: {
    safe: {
      ewgScore: "1",
      ewgLabel: "Low Hazard",
      certifications: [
        { label: "EWG Verified",          tooltip: "Meets EWG's strictest standards for ingredient safety" },
        { label: "Dermatologist Tested",  tooltip: "Clinically tested by board-certified dermatologists" },
        { label: "Fragrance Free",        tooltip: "Contains no added fragrance or parfum" },
      ],
      regulations: [
        { label: "EU Compliant",          tooltip: "Meets EU cosmetic safety regulations (1,600+ banned ingredients)" },
        { label: "California Safe",       tooltip: "Complies with California Toxic-Free Cosmetics Act" },
      ],
    },

    does: {
      benefits: [
        { label: "Buildable Color",       tooltip: "Sheer to medium coverage depending on how much you layer" },
        { label: "Natural Flush",         tooltip: "Mimics the look of naturally flushed skin" },
        { label: "Hydrating",             tooltip: "Jojoba oil keeps skin moisturized throughout the day" },
        { label: "Long-wearing",          tooltip: "Up to 8 hours wear time in clinical testing" },
        { label: "Non-comedogenic",       tooltip: "Won't clog pores — tested and confirmed" },
      ],
    },

    for: {
      skinTypes: [
        { label: "Dry Skin",              tooltip: "Cream formula is especially flattering on dry skin" },
        { label: "Normal Skin",           tooltip: "Works well with normal skin types" },
        { label: "Sensitive Skin",        tooltip: "Free of known irritants, suitable for sensitive skin" },
      ],
      personas: [
        { label: "Clean Beauty Curious",  tooltip: "Great entry point for people new to clean beauty" },
        { label: "Minimalist",            tooltip: "Does double duty as blush + lip color" },
      ],
      notFor: [
        { label: "Oily Skin",             tooltip: "Cream formulas may not last as long on oily skin — set with powder" },
      ],
    },

    is: {
      keyIngredients: [
        {
          label: "Castor Seed Oil",
          inci: "Ricinus Communis Seed Oil",
          slug: "castor-seed-oil",
          tooltip: "Ricinus Communis Seed Oil — Emollient base. Gives the formula its glide.",
        },
        {
          label: "Jojoba Oil",
          inci: "Simmondsia Chinensis Seed Oil",
          slug: "jojoba-oil",
          tooltip: "Simmondsia Chinensis Seed Oil — Technically a wax ester. Mimics skin's own sebum.",
        },
        {
          label: "Caprylic/Capric Triglyceride",
          inci: "Caprylic/Capric Triglyceride",
          slug: "caprylic-capric-triglyceride",
          tooltip: "Caprylic/Capric Triglyceride — Lightweight emollient from coconut oil.",
        },
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
        { label: "Credo Beauty",     url: "#", tooltip: "Ships free over $50. Credo Clean Standard verified." },
        { label: "Tower 28 Direct",  url: "#", tooltip: "Buy direct from the brand. Subscribe & save 15%." },
        { label: "Sephora",          url: "#", tooltip: "In-store and online. Free samples with orders." },
      ],
      affiliateNote: "DHG earns a small commission when you shop these links — disclosed because that's the whole point.",
    },
  },
};

/* ─────────────────────────────────────────
   PILL COMPONENT
───────────────────────────────────────── */
function Pill({ label, color, tooltip, isLink }) {
  const [showTip, setShowTip] = useState(false);

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <span
        onMouseEnter={() => setShowTip(true)}
        onMouseLeave={() => setShowTip(false)}
        style={{
          display: "inline-block",
          padding: "4px 10px",
          borderRadius: 9999,
          fontSize: ".72rem",
          fontFamily: "'Outfit', sans-serif",
          fontWeight: 600,
          color: isLink ? COLORS.rabbitHole : color,
          background: isLink ? "rgba(255,140,42,.12)" : `${color}18`,
          border: `1px solid ${isLink ? COLORS.rabbitHole : color}40`,
          cursor: isLink ? "pointer" : "default",
          whiteSpace: "nowrap",
          transition: "all 0.15s ease",
        }}
      >
        {isLink ? `${label} →` : label}
      </span>

      {showTip && tooltip && (
        <div style={{
          position: "absolute",
          bottom: "calc(100% + 6px)",
          left: 0,
          zIndex: 200,
          background: "rgba(255,255,255,.96)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(0,0,0,.1)",
          borderRadius: 12,
          padding: "8px 12px",
          minWidth: 180,
          maxWidth: 240,
          pointerEvents: "none",
          boxShadow: "0 4px 20px rgba(0,0,0,.3)",
        }}>
          <div style={{
            fontSize: ".72rem",
            color: "#333",
            fontFamily: "'Outfit', sans-serif",
            lineHeight: 1.5,
          }}>
            {tooltip}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────
   SUB-LABEL (Space Mono category labels)
───────────────────────────────────────── */
function SubLabel({ text }) {
  return (
    <div style={{
      fontSize: ".6rem",
      fontFamily: "'Space Mono', monospace",
      color: COLORS.grey,
      textTransform: "uppercase",
      letterSpacing: ".05em",
      marginBottom: 5,
    }}>
      {text}
    </div>
  );
}

/* ─────────────────────────────────────────
   SECTION CONTENT — per section type
───────────────────────────────────────── */
function SectionContent({ sectionKey, data }) {
  if (sectionKey === "safe") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {/* EWG Score */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            fontFamily: "'Space Mono', monospace",
            fontSize: ".95rem",
            fontWeight: 700,
            color: COLORS.isItSafe,
          }}>
            EWG {data.ewgScore}
          </span>
          <span style={{
            fontFamily: "'Space Mono', monospace",
            fontSize: ".65rem",
            color: COLORS.grey,
            textTransform: "uppercase",
            letterSpacing: ".05em",
          }}>
            {data.ewgLabel}
          </span>
        </div>

        {/* Certifications */}
        <div>
          <SubLabel text="Certifications" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {data.certifications.map((c, i) => (
              <Pill key={i} label={c.label} color={COLORS.isItSafe} tooltip={c.tooltip} />
            ))}
          </div>
        </div>

        {/* Regulations */}
        <div>
          <SubLabel text="Regulatory" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {data.regulations.map((r, i) => (
              <Pill key={i} label={r.label} color={COLORS.isItSafe} tooltip={r.tooltip} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (sectionKey === "does") {
    return (
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
        {data.benefits.map((b, i) => (
          <Pill key={i} label={b.label} color={COLORS.whatItDoes} tooltip={b.tooltip} />
        ))}
      </div>
    );
  }

  if (sectionKey === "for") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {data.skinTypes.map((s, i) => (
            <Pill key={i} label={s.label} color={COLORS.whoItsFor} tooltip={s.tooltip} />
          ))}
          {data.personas.map((p, i) => (
            <Pill key={i} label={p.label} color={COLORS.whoItsFor} tooltip={p.tooltip} />
          ))}
        </div>

        {data.notFor.length > 0 && (
          <div>
            <SubLabel text="Not ideal for" />
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {data.notFor.map((n, i) => (
                <Pill key={i} label={n.label} color={COLORS.grey} tooltip={n.tooltip} />
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  if (sectionKey === "is") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>

        {/* Key Ingredients — AQUA rabbit hole links */}
        <div>
          <SubLabel text="Key Ingredients" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {data.keyIngredients.map((ing, i) => (
              <Pill
                key={i}
                label={ing.label}
                color={COLORS.ingredients}
                tooltip={ing.tooltip}
                isLink={true}
              />
            ))}
          </div>
        </div>

        {/* Formula Base — BLUE */}
        <div>
          <SubLabel text="Formula Base" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {data.formulaBase.map((f, i) => (
              <Pill key={i} label={f.label} color={COLORS.packaging} tooltip={f.tooltip} />
            ))}
          </div>
        </div>

        {/* Packaging — BLUE */}
        <div>
          <SubLabel text="Packaging" />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {data.packaging.map((p, i) => (
              <Pill key={i} label={p.label} color={COLORS.packaging} tooltip={p.tooltip} />
            ))}
          </div>
        </div>

      </div>
    );
  }

  if (sectionKey === "deal") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>

        {/* Price block */}
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span style={{
            fontFamily: "'Outfit', sans-serif",
            fontWeight: 900,
            fontSize: "1.3rem",
            color: "rgba(255,255,255,.75)",
          }}>
            {data.price}
          </span>
          <span style={{
            fontFamily: "'Outfit', sans-serif",
            fontSize: ".72rem",
            color: COLORS.grey,
          }}>
            {data.pricePerOz} · {data.priceTier}
          </span>
        </div>

        {/* Retailer links — rabbit hole orange */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {data.retailers.map((r, i) => (
            <a
              key={i}
              href={r.url}
              title={r.tooltip}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "9px 12px",
                borderRadius: 8,
                background: "rgba(255,140,42,.06)",
                border: "1px solid rgba(255,140,42,.25)",
                textDecoration: "none",
                transition: "background 0.15s",
              }}
            >
              <span style={{
                fontFamily: "'Outfit', sans-serif",
                fontSize: ".8rem",
                fontWeight: 600,
                color: COLORS.rabbitHole,
              }}>
                {r.label}
              </span>
              <span style={{ fontSize: 12, color: COLORS.rabbitHole }}>→</span>
            </a>
          ))}
        </div>

        {/* Affiliate disclosure */}
        <div style={{
          fontSize: ".6rem",
          fontFamily: "'Space Mono', monospace",
          color: COLORS.grey,
          lineHeight: 1.6,
          paddingTop: 6,
          borderTop: `1px solid ${COLORS.divider}`,
        }}>
          {data.affiliateNote}
        </div>

      </div>
    );
  }

  return null;
}

/* ─────────────────────────────────────────
   SECTION WRAPPER
───────────────────────────────────────── */
function Section({ section, data, isOpen, onToggle }) {
  return (
    <div style={{ borderTop: `1px solid ${COLORS.divider}` }}>

      {/* Section header / toggle */}
      <button
        onClick={onToggle}
        style={{
          width: "100%",
          padding: "10px 16px",
          background: isOpen ? `${section.color}0e` : "transparent",
          border: "none",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: 8,
          transition: "background 0.2s",
        }}
      >
        <span style={{
          fontSize: ".72rem",
          fontFamily: "'Outfit', sans-serif",
          fontWeight: 700,
          letterSpacing: ".06em",
          textTransform: "uppercase",
          color: isOpen ? section.color : "rgba(255,255,255,.45)",
          flex: 1,
          textAlign: "left",
          transition: "color 0.2s",
        }}>
          {section.label}
        </span>

        <span style={{
          fontSize: 9,
          color: "rgba(255,255,255,.2)",
          transform: isOpen ? "rotate(90deg)" : "none",
          transition: "transform 0.2s",
          display: "inline-block",
        }}>
          ▶
        </span>
      </button>

      {/* Collapsible content */}
      <div style={{
        maxHeight: isOpen ? 500 : 0,
        overflow: "hidden",
        transition: "max-height 0.3s ease",
      }}>
        <div style={{ padding: "2px 16px 14px" }}>
          <SectionContent sectionKey={section.key} data={data} />
        </div>
      </div>

    </div>
  );
}

/* ─────────────────────────────────────────
   MAIN COMPONENT
   Props:
     product   — CMS-bound product object (defaults to sampleProduct)
     onFlipBack — callback to flip card back to front
───────────────────────────────────────── */
export default function ProductFactsBack({ product = sampleProduct, onFlipBack }) {
  // IS IT SAFE? open by default — safety first
  const [openSection, setOpenSection] = useState("safe");

  const toggleSection = (key) => {
    setOpenSection(openSection === key ? null : key);
  };

  return (
    <div style={{
      width: "100%",
      maxWidth: 380,
      background: COLORS.bg,
      color: COLORS.white,
      fontFamily: "'Outfit', sans-serif",
      overflowY: "auto",
      maxHeight: "calc(100dvh - 90px)", // room for header + footer
      // Scrollbar hidden
      scrollbarWidth: "none",
      msOverflowStyle: "none",
    }}>

      {/* ── Header ── */}
      <div style={{ padding: "14px 16px 10px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            {/* "Product Facts" label */}
            <div style={{
              fontFamily: "'Space Mono', monospace",
              fontSize: ".6rem",
              color: COLORS.grey,
              textTransform: "uppercase",
              letterSpacing: ".1em",
              marginBottom: 4,
            }}>
              Product Facts
            </div>

            {/* Product name */}
            <div style={{
              fontSize: "1.1rem",
              fontWeight: 900,
              color: COLORS.white,
              lineHeight: 1.2,
            }}>
              {product.name}
            </div>

            {/* Brand — rabbit hole link */}
            <a
              href={`/brands/${product.brandSlug}`}
              style={{
                fontSize: ".85rem",
                fontWeight: 700,
                color: COLORS.rabbitHole,
                textDecoration: "none",
                display: "inline-block",
                marginTop: 2,
              }}
            >
              {product.brand} →
            </a>
          </div>

          {/* Flip back button */}
          <button
            onClick={onFlipBack}
            style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: "rgba(255,255,255,.06)",
              border: "1px solid rgba(255,255,255,.1)",
              color: "rgba(255,255,255,.4)",
              fontSize: 14,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            ↺
          </button>
        </div>

        {/* Meta row */}
        <div style={{
          fontSize: ".68rem",
          color: "rgba(255,255,255,.35)",
          marginTop: 6,
        }}>
          {product.category} · {product.type}&nbsp;&nbsp;|&nbsp;&nbsp;{product.size}&nbsp;&nbsp;|&nbsp;&nbsp;{product.price}
        </div>
      </div>

      {/* ── Thick rule ── */}
      <div style={{ height: 1, background: "rgba(255,255,255,.2)", margin: "0 16px" }} />

      {/* ── Five Sections ── */}
      <div>
        {SECTIONS.map((section) => (
          <Section
            key={section.key}
            section={section}
            data={product.sections[section.key]}
            isOpen={openSection === section.key}
            onToggle={() => toggleSection(section.key)}
          />
        ))}
      </div>

      {/* ── Verified footer ── */}
      <div style={{
        textAlign: "center",
        padding: "12px 16px 16px",
        borderTop: `1px solid ${COLORS.divider}`,
        marginTop: 4,
      }}>
        <span style={{
          fontFamily: "'Space Mono', monospace",
          fontSize: ".65rem",
          color: COLORS.grey,
          letterSpacing: ".06em",
          textTransform: "uppercase",
        }}>
          Verified {product.verified}
        </span>
      </div>

    </div>
  );
}
