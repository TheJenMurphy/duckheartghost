"use client";

import { useState, useRef, useCallback } from "react";

/* ── Types ── */
interface PillItem {
  label: string;
  tooltip: string;
}

export interface Brand {
  id: string;
  name: string;
  tagline: string;
  founded: string;
  location: string;
  priceRange: string;
  galleryImages: string[];
  voteData: { duck: number; heart: number; ghost: number };
  description: string;
  values: PillItem[];
  certifications: PillItem[];
  keyProducts: PillItem[];
  keyIngredients: PillItem[];
  ownership: PillItem[];
  controversies: string[];
  verified: string;
}

/* ── Main Card ── */
export default function BrandCard({ brand }: { brand: Brand }) {
  const [flipped, setFlipped] = useState(false);
  const [voted, setVoted] = useState<string | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const segRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const flipCard = () => setFlipped((f) => !f);

  const castVote = (vote: string) => {
    setVoted(vote);
    const seg = segRefs.current[vote];
    if (!seg) return;
    const glowColors: Record<string, string> = {
      duck: "rgba(255,170,0,.9)",
      heart: "rgba(255,68,102,.9)",
      ghost: "rgba(153,85,255,.9)",
    };
    const color = glowColors[vote];
    let step = 0;
    const timer = setInterval(() => {
      step++;
      const i = step <= 5 ? step : 10 - step;
      seg.style.boxShadow = `0 0 ${i * 5}px ${i * 2}px ${color}`;
      if (step >= 10) {
        clearInterval(timer);
        setTimeout(() => {
          seg.style.transition = "box-shadow 2s ease";
          seg.style.boxShadow = "none";
        }, 1200);
      }
    }, 80);
  };

  return (
    <div className="card-unit" ref={cardRef}>
      {/* ── Header ── */}
      <div className="card-header">
        <div className="site-header-inner">
          <div className="rainbow-bar" />
          <div className="nav-inner">
            <button className="nav-btn flip" onClick={flipCard} style={{ fontSize: "1.8rem" }}>
              ⟲
            </button>
            <button className="nav-btn">🐇</button>
            <button className="nav-btn">🪞</button>
            <button className="nav-btn">🔍</button>
            <button className="nav-btn active">❤️</button>
          </div>
        </div>
      </div>

      {/* ── Body — 3D flip ── */}
      <div className="card-body">
        <div className={`card-flipper${flipped ? " flipped" : ""}`}>
          {/* ======= FRONT ======= */}
          <div className="card-slide">
            <div className="gallery-wrapper">
              <div className="gallery">
                {brand.galleryImages.map((src, i) => (
                  <div className="gallery-slide" key={i}>
                    <img src={src} alt={`${brand.name} ${i + 1}`} className="gallery-img" />
                  </div>
                ))}
              </div>
            </div>
            <div className="front-body" style={{ justifyContent: "flex-start", flex: "none", paddingTop: 16 }}>
              {/* Vote hint or results */}
              {!voted ? (
                <div className="vote-hint" style={{ paddingBottom: 0, marginBottom: 12 }}>vote to see if the hive agrees</div>
              ) : (
                <div style={{ marginBottom: 8 }}>
                  <div className="vote-bar">
                    <div className="vote-seg" ref={(el) => { segRefs.current.duck = el; }} style={{ flex: brand.voteData.duck, background: "var(--duck)" }} />
                    <div style={{ width: 2, background: "#111", flexShrink: 0 }} />
                    <div className="vote-seg" ref={(el) => { segRefs.current.heart = el; }} style={{ flex: brand.voteData.heart, background: "var(--heart)" }} />
                    <div style={{ width: 2, background: "#111", flexShrink: 0 }} />
                    <div className="vote-seg" ref={(el) => { segRefs.current.ghost = el; }} style={{ flex: brand.voteData.ghost, background: "var(--ghost)" }} />
                  </div>
                  <div className="vote-pct-row">
                    {(["duck", "heart", "ghost"] as const).map((v) => (
                      <span key={v} className="vote-pct" style={{ color: `var(--${v})`, fontSize: voted === v ? ".78rem" : ".62rem", opacity: voted === v ? 1 : 0.6 }}>
                        {v === "duck" ? "🦆" : v === "heart" ? "❤️" : "👻"} {brand.voteData[v]}%
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Brand name */}
              <div style={{
                fontSize: "1.45rem", fontWeight: 800, color: "#fff",
                letterSpacing: "-.03em", lineHeight: 1.15, marginBottom: 3,
              }}>
                {brand.name}
              </div>

              {/* Tagline */}
              <div style={{ fontSize: ".95rem", color: "rgba(255,255,255,.45)", marginBottom: 10 }}>
                {brand.tagline}
              </div>

              {/* Meta — stacked */}
              <div style={{ fontSize: ".78rem", color: "#aaa", display: "flex", flexDirection: "column", gap: 6 }}>
                <span>Est. {brand.founded} · {brand.location}</span>
                <span>{brand.priceRange}</span>
              </div>

              {/* Tap for Facts */}
              <div className="flip-hint" onClick={flipCard} style={{ cursor: "pointer", marginTop: 14 }}>
                Tap ↺ for Facts
              </div>
            </div>
          </div>

          {/* ======= BACK — Brand Facts ======= */}
          <div className="card-slide back">
            <div className="back-body">
              <div className="back-title">Brand Facts</div>
              <div className="back-rule" />
              <div className="back-product">{brand.name}</div>
              <div style={{ fontSize: ".85rem", color: "rgba(255,255,255,.45)", marginBottom: 3 }}>
                {brand.tagline}
              </div>
              <div className="back-meta-row">
                <span>Est. {brand.founded}</span>
                <span>{brand.location}</span>
                <span>{brand.priceRange}</span>
              </div>

              {/* Description */}
              <div className="section-line" />
              <div className="section-row">
                <div style={{ fontSize: ".85rem", color: "rgba(255,255,255,.7)", lineHeight: 1.5 }}>
                  {brand.description}
                </div>
              </div>

              {/* Values */}
              <PillSection label="Values" color="var(--s-benefits)" pills={brand.values} cardRef={cardRef} wrap />

              {/* Ownership */}
              <PillSection label="Ownership" color="var(--ghost)" pills={brand.ownership} cardRef={cardRef} />

              {/* Certifications */}
              <PillSection label="Certifications" color="var(--s-certs)" pills={brand.certifications} cardRef={cardRef} wrap />

              {/* Key Products */}
              <PillSection label="Key Products" color="var(--rabbit)" pills={brand.keyProducts} cardRef={cardRef} seeAll />

              {/* Key Ingredients */}
              <PillSection label="Key Ingredients" color="var(--s-ingredients)" pills={brand.keyIngredients} cardRef={cardRef} />

              {/* Controversies / Transparency */}
              {brand.controversies.length > 0 && (
                <>
                  <div className="section-line" />
                  <div className="section-row">
                    <div className="section-label">
                      🧂 Transparency <span className="section-arrow" style={{ color: "var(--heart)" }}>▶</span>
                    </div>
                    {brand.controversies.map((c, i) => (
                      <div key={i} style={{ fontSize: ".8rem", color: "rgba(255,255,255,.5)", marginBottom: 3, lineHeight: 1.4 }}>
                        △ {c}
                      </div>
                    ))}
                  </div>
                </>
              )}

              <div className="back-verified">Verified {brand.verified} · 🧂 = conflict</div>
            </div>
          </div>
        </div>
      </div>

	{/* ── Footer ── */}
      <div className="card-footer">
        <div className="dhg-buttons">
          {([["duck", "🦆"], ["heart", "❤️"], ["ghost", "👻"]] as const).map(([key, emoji]) => (
            <button key={key} className={`dhg-btn ${key}`} onClick={() => castVote(key)}>
              <div className="dhg-btn-inner">{emoji}</div>
            </button>
          ))}
        </div>
	<button className="shop-btn">
          <div className="shop-btn-inner">
            <span>👜</span>
            <span className="shop-label">Shop &amp; Support</span>
          </div>
        </button>
      </div>
    </div>
  );
}

/* ── Pill Section ── */
function PillSection({
  label, color, pills, cardRef, wrap, seeAll,
}: {
  label: string; color: string; pills: PillItem[];
  cardRef: React.RefObject<HTMLDivElement | null>;
  wrap?: boolean; seeAll?: boolean;
}) {
  return (
    <>
      <div className="section-line" />
      <div className="section-row">
        <div className="section-label">
          {label} <span className="section-arrow" style={{ color }}>▶</span>
        </div>
        <div className={`pill-row${wrap ? " wrap" : ""}`}>
          {pills.map((p) => (
            <Tooltip key={p.label} label={p.label} tooltip={p.tooltip} color={color} cardRef={cardRef} />
          ))}
        </div>
        {seeAll && <a href="#" className="see-all">See all products →</a>}
      </div>
    </>
  );
}

/* ── Tooltip Pill ── */
function Tooltip({
  label, tooltip, color, cardRef,
}: {
  label: string; tooltip: string; color: string;
  cardRef: React.RefObject<HTMLDivElement | null>;
}) {
  const tipRef = useRef<HTMLSpanElement>(null);

  const handleMouseEnter = useCallback(() => {
    const box = tipRef.current?.querySelector(".tipbox") as HTMLElement | null;
    if (!box || !cardRef.current) return;
    box.style.left = "0"; box.style.right = "auto";
    const rect = box.getBoundingClientRect();
    const cardRect = cardRef.current.getBoundingClientRect();
    if (rect.right > cardRect.right - 8) { box.style.left = "auto"; box.style.right = "0"; }
    if (rect.left < cardRect.left + 8) { box.style.left = "0"; box.style.right = "auto"; }
  }, [cardRef]);

  return (
    <span className="tip" ref={tipRef} onMouseEnter={handleMouseEnter}>
      <span className="pill" style={{ "--c": color } as React.CSSProperties}>{label}</span>
      <span className="tipbox">
        <div className="tipbox-term">{label}</div>
        <div className="tipbox-body">{tooltip}</div>
      </span>
    </span>
  );
}
