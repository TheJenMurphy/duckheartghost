"use client";

import { useState, useRef, useCallback } from "react";

/* ── 9S Color System ── */
const S9: Record<string, string> = {
  stars:          "#ed8435",
  source:         "#e35e2e",
  safety:         "#e9455c",
  support:        "#d94d85",
  suitability:    "#bf5cc9",
  structure:      "#886de1",
  substance:      "#3f8def",
  sustainability: "#79c2ef",
  spend:          "#59c2d5",
};

/* ── Five Drawer Config ── */
const DRAWERS = [
  { key: "receipts", label: "Receipts",  emoji: "\u{1F9FE}", color: S9.stars,          desc: "Stars \u00B7 Source \u00B7 Safety" },
  { key: "science",  label: "Science",   emoji: "\u{1F52C}", color: S9.substance,      desc: "Substance \u00B7 Structure" },
  { key: "match",    label: "Match",     emoji: "\u{1F3AF}", color: S9.suitability,    desc: "Suitability \u00B7 Support" },
  { key: "impact",   label: "Impact",    emoji: "\u{1F33F}", color: S9.sustainability, desc: "Sustainability" },
  { key: "deal",     label: "Deal",      emoji: "\u{1F4B0}", color: S9.spend,          desc: "Spend" },
];

interface PillData {
  label: string;
  tooltip: string;
}

/* ── Sample product data ── */
const sampleProduct = {
  name: "BeachPlease Cream Blush",
  brand: "Tower 28",
  price: "$20",
  verified: "Feb 2026",

  drawers: {
    receipts: {
      stars: [
        { label: "4.6 \u2605 Sephora", tooltip: "Based on 2,400+ reviews on Sephora.com" },
        { label: "4.8 \u2605 Credo", tooltip: "Based on 180 reviews on Credo Beauty" },
        { label: "Allure Best of Beauty", tooltip: "Winner 2023 Allure Best of Beauty Awards" },
      ],
      source: [
        { label: "Women Owned", tooltip: "Founded by Amy Liu in 2019" },
        { label: "Made in USA", tooltip: "Manufactured in Los Angeles, CA" },
        { label: "BIPOC Founded", tooltip: "Amy Liu is a Chinese-American founder" },
      ],
      safety: [
        { label: "Pregnancy Safe", tooltip: "No retinoids, salicylic acid, or harmful ingredients" },
        { label: "Sensitive Safe", tooltip: "NEA accepted for sensitive and eczema-prone skin" },
        { label: "Allergy Tested", tooltip: "Dermatologist tested and approved for reactive skin" },
      ],
    },
    science: {
      structure: [
        { label: "Cream", tooltip: "Cream-to-powder finish blends seamlessly" },
        { label: "Buildable", tooltip: "Sheer to medium coverage, layer for intensity" },
        { label: "Multi-use", tooltip: "Works on cheeks, lips, and eyelids" },
      ],
      substance: [
        { label: "Aloe Vera", tooltip: "Soothing botanical, calms redness" },
        { label: "Green Tea", tooltip: "Antioxidant protection" },
        { label: "Apricot Oil", tooltip: "Vitamin E rich, nourishing emollient" },
      ],
    },
    match: {
      suitability: [
        { label: "All Skin Types", tooltip: "Tested across oily, dry, combination, and sensitive" },
        { label: "Light\u2013Deep", tooltip: "6 shades ranging from fair to deep skin tones" },
        { label: "Warm & Cool", tooltip: "Shade range covers warm, neutral, and cool undertones" },
      ],
      support: [
        { label: "Hydrating", tooltip: "Adds moisture without caking or drying" },
        { label: "Long Lasting", tooltip: "Wears 6-8 hours without touchup" },
        { label: "Brightening", tooltip: "Natural radiant finish, not glittery" },
      ],
    },
    impact: {
      sustainability: [
        { label: "Recyclable", tooltip: "Compact is post-consumer recycled plastic" },
        { label: "Leaping Bunny", tooltip: "Certified cruelty-free by Leaping Bunny" },
        { label: "Clean at Sephora", tooltip: "No parabens, sulfates, phthalates" },
      ],
    },
    deal: {
      spend: [
        { label: "Accessible \u00B7 $20", tooltip: "Under $25 price point" },
        { label: "Credo \u00B7 $20", tooltip: "Available at Credo Beauty" },
        { label: "Sephora \u00B7 $20", tooltip: "Available at Sephora" },
        { label: "0.17 oz", tooltip: "Standard blush compact, lasts 4-6 months" },
      ],
    },
  } as Record<string, Record<string, PillData[]>>,

  realTalk: [
    { label: "\u{1F986} Shade range could be wider", type: "duck" },
    { label: "\u2764\uFE0F Best drugstore-priced clean blush", type: "heart" },
    { label: "\u{1F47B} Packaging feels cheap for the price", type: "ghost" },
  ],
  conflicts: "Tower 28 affiliate \u00B7 Credo affiliate",
};

/* ── Page Component ── */
export default function TestBackPage() {
  const [openDrawer, setOpenDrawer] = useState<string | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  const toggleDrawer = (key: string) => {
    setOpenDrawer(openDrawer === key ? null : key);
  };

  const rainbow = Object.values(S9);

  return (
    <div style={{
      display: "flex", justifyContent: "center", alignItems: "flex-start",
      minHeight: "100vh", background: "#181819",
      fontFamily: "'DM Sans', -apple-system, sans-serif",
      padding: "40px 20px",
    }}>
      <div ref={cardRef} style={{
        width: 375, maxWidth: "100%", borderRadius: 20, overflow: "hidden",
        background: "#000",
        border: "1px solid rgba(255,255,255,0.06)",
        boxShadow: "0 24px 80px rgba(0,0,0,0.6)",
      }}>
        {/* Rainbow bar */}
        <div style={{ height: 3, background: `linear-gradient(90deg, ${rainbow.join(", ")})` }} />

        {/* Back Header */}
        <div style={{
          padding: "14px 20px 12px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <div>
            <div style={{
              fontFamily: "'Space Mono', monospace", fontSize: 9,
              color: "rgba(255,255,255,.3)", textTransform: "uppercase" as const,
              letterSpacing: 2, marginBottom: 2,
            }}>
              Product Facts
            </div>
            <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "#fff", lineHeight: 1.2 }}>
              {sampleProduct.name}
            </div>
            <div style={{ fontSize: ".82rem", color: "rgba(255,255,255,.4)", marginTop: 2 }}>
              {sampleProduct.brand} &middot; {sampleProduct.price}
            </div>
          </div>
          <div style={{
            width: 32, height: 32, borderRadius: "50%",
            background: "rgba(255,255,255,0.06)",
            border: "1px solid rgba(255,255,255,0.1)",
            color: "rgba(255,255,255,0.4)", fontSize: 14,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            &#x21BB;
          </div>
        </div>

        {/* 9S Mini Icons Row */}
        <div style={{
          display: "flex", justifyContent: "center", gap: 4,
          padding: "10px 16px 6px",
        }}>
          {Object.entries(S9).map(([name, color]) => (
            <div key={name} style={{
              width: 28, height: 28, borderRadius: "50%",
              background: `${color}22`,
              border: `1.5px solid ${color}55`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 8, fontWeight: 700, color: color,
              textTransform: "uppercase" as const,
              fontFamily: "'Space Mono', monospace",
            }}>
              {name.charAt(0).toUpperCase()}
            </div>
          ))}
        </div>

        {/* ── Five Drawers ── */}
        <div style={{ padding: "6px 0" }}>
          {DRAWERS.map((drawer) => {
            const isOpen = openDrawer === drawer.key;
            const drawerData = sampleProduct.drawers[drawer.key];

            return (
              <div key={drawer.key}>
                <button
                  onClick={() => toggleDrawer(drawer.key)}
                  style={{
                    width: "100%", padding: "10px 20px",
                    background: isOpen ? `${drawer.color}12` : "transparent",
                    border: "none", borderTop: "1px solid rgba(255,255,255,0.04)",
                    cursor: "pointer",
                    display: "flex", alignItems: "center", gap: 10,
                    transition: "all 0.2s ease",
                  }}
                >
                  <div style={{
                    width: 3, height: 24, borderRadius: 2,
                    background: drawer.color,
                    opacity: isOpen ? 1 : 0.4,
                    transition: "opacity 0.2s",
                  }} />
                  <span style={{ fontSize: 16 }}>{drawer.emoji}</span>
                  <div style={{ flex: 1, textAlign: "left" as const }}>
                    <div style={{
                      fontSize: ".82rem", fontWeight: 700,
                      color: isOpen ? drawer.color : "rgba(255,255,255,.7)",
                      letterSpacing: ".03em", transition: "color 0.2s",
                    }}>
                      {drawer.label}
                    </div>
                    <div style={{
                      fontSize: ".65rem", color: "rgba(255,255,255,.25)",
                      fontFamily: "'Space Mono', monospace", letterSpacing: ".5px",
                    }}>
                      {drawer.desc}
                    </div>
                  </div>
                  <span style={{
                    fontSize: 12, color: "rgba(255,255,255,.3)",
                    transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
                    transition: "transform 0.2s", display: "inline-block",
                  }}>
                    &#x25B6;
                  </span>
                </button>

                <div style={{
                  maxHeight: isOpen ? 400 : 0,
                  overflow: "hidden",
                  transition: "max-height 0.3s ease",
                  background: "rgba(255,255,255,0.02)",
                }}>
                  <div style={{ padding: "8px 20px 14px" }}>
                    {Object.entries(drawerData).map(([category, pills]) => (
                      <div key={category} style={{ marginBottom: 10 }}>
                        <div style={{
                          fontSize: ".65rem", fontWeight: 700,
                          color: S9[category],
                          textTransform: "uppercase" as const,
                          letterSpacing: "1.5px",
                          fontFamily: "'Space Mono', monospace",
                          marginBottom: 6,
                          display: "flex", alignItems: "center", gap: 6,
                        }}>
                          <span style={{
                            width: 6, height: 6, borderRadius: "50%",
                            background: S9[category], display: "inline-block",
                          }} />
                          {category}
                        </div>
                        <div style={{ display: "flex", flexWrap: "wrap" as const, gap: 5 }}>
                          {(pills as PillData[]).map((pill) => (
                            <PillWithTooltip
                              key={pill.label}
                              label={pill.label}
                              tooltip={pill.tooltip}
                              color={S9[category]}
                              cardRef={cardRef}
                            />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* ── Real Talk ── */}
        <div style={{
          borderTop: "1px solid rgba(255,255,255,0.06)",
          padding: "12px 20px",
        }}>
          <div style={{
            fontSize: ".7rem", fontWeight: 700,
            color: "rgba(255,255,255,.3)",
            textTransform: "uppercase" as const,
            letterSpacing: "1.5px",
            fontFamily: "'Space Mono', monospace",
            marginBottom: 8,
          }}>
            Real Talk
          </div>
          <div style={{ display: "flex", flexDirection: "column" as const, gap: 5 }}>
            {sampleProduct.realTalk.map((tag, i) => (
              <div key={i} style={{
                fontSize: ".78rem",
                color: tag.type === "duck" ? "#c6a350"
                     : tag.type === "heart" ? "#e9455c"
                     : "#886de1",
                lineHeight: 1.4,
              }}>
                {tag.label}
              </div>
            ))}
          </div>
        </div>

        {/* ── Conflict Disclosure ── */}
        <div style={{
          borderTop: "1px solid rgba(255,255,255,0.04)",
          padding: "10px 20px 14px",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <div style={{
            fontSize: ".65rem", color: "rgba(255,255,255,.2)",
            fontFamily: "'Space Mono', monospace",
          }}>
            &#x1F9C2; {sampleProduct.conflicts}
          </div>
          <div style={{
            fontSize: ".6rem", color: "rgba(255,255,255,.15)",
            fontFamily: "'Space Mono', monospace",
          }}>
            Verified {sampleProduct.verified}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Pill with Tooltip ── */
function PillWithTooltip({ label, tooltip, color, cardRef }: {
  label: string; tooltip: string; color: string;
  cardRef: React.RefObject<HTMLDivElement | null>;
}) {
  const [showTip, setShowTip] = useState(false);
  const pillRef = useRef<HTMLSpanElement>(null);
  const [tipLeft, setTipLeft] = useState(0);

  const handleEnter = useCallback(() => {
    setShowTip(true);
    if (pillRef.current && cardRef.current) {
      const pillRect = pillRef.current.getBoundingClientRect();
      const cardRect = cardRef.current.getBoundingClientRect();
      const tipWidth = 220;
      let left = 0;
      if (pillRect.left + tipWidth > cardRect.right - 12) {
        left = cardRect.right - pillRect.left - tipWidth - 12;
      }
      setTipLeft(left);
    }
  }, [cardRef]);

  return (
    <span
      ref={pillRef}
      style={{ position: "relative", display: "inline-block" }}
      onMouseEnter={handleEnter}
      onMouseLeave={() => setShowTip(false)}
    >
      <span style={{
        display: "inline-block",
        padding: "3px 10px",
        borderRadius: 20,
        fontSize: ".72rem",
        fontWeight: 500,
        background: `${color}15`,
        color: color,
        border: `1px solid ${color}33`,
        cursor: "pointer",
        transition: "all 0.15s ease",
        whiteSpace: "nowrap" as const,
      }}>
        {label}
      </span>

      {showTip && (
        <span style={{
          position: "absolute" as const,
          bottom: "calc(100% + 6px)",
          left: tipLeft,
          width: 220,
          padding: "8px 10px",
          borderRadius: 8,
          background: "rgba(20,20,25,0.95)",
          border: `1px solid ${color}44`,
          backdropFilter: "blur(12px)",
          zIndex: 100,
          boxShadow: `0 4px 20px rgba(0,0,0,0.4), 0 0 0 1px ${color}22`,
        }}>
          <div style={{
            fontSize: ".7rem", fontWeight: 700, color: color,
            marginBottom: 3, letterSpacing: ".03em",
          }}>
            {label}
          </div>
          <div style={{
            fontSize: ".68rem", color: "rgba(255,255,255,.6)",
            lineHeight: 1.45,
          }}>
            {tooltip}
          </div>
        </span>
      )}
    </span>
  );
}
