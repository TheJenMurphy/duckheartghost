"use client";

import { useState, useRef, useCallback } from "react";

/* ── Types ── */
interface PillItem {
  label: string;
  tooltip: string;
}

export interface Ingredient {
  id: string;
  inci: string;
  aka: string;
  type: "Synthetic" | "Botanical";
  kind: string;
  origin: string;
  galleryImages: string[];
  voteData: { duck: number; heart: number; ghost: number };
  description: string;
  concentration: string;
  ph: string;
  solubility: string;
  comedogenicRating: string;
  ewgScore: string;
  functions: PillItem[];
  pairsWell: PillItem[];
  avoidWith: PillItem[];
  foundIn: PillItem[];
  regStatus: { region: string; status: "permitted" | "restricted" | "banned" }[];
  sources: { title: string; journal: string; year: number }[];
  verified: string;
}

/* ── Main Card ── */
export default function IngredientCard({ ingredient }: { ingredient: Ingredient }) {
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
                {ingredient.galleryImages.map((src, i) => (
                  <div className="gallery-slide" key={i}>
                    <img src={src} alt={`${ingredient.inci} ${i + 1}`} className="gallery-img" />
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
                    <div className="vote-seg" ref={(el) => { segRefs.current.duck = el; }} style={{ flex: ingredient.voteData.duck, background: "var(--duck)" }} />
                    <div style={{ width: 2, background: "#111", flexShrink: 0 }} />
                    <div className="vote-seg" ref={(el) => { segRefs.current.heart = el; }} style={{ flex: ingredient.voteData.heart, background: "var(--heart)" }} />
                    <div style={{ width: 2, background: "#111", flexShrink: 0 }} />
                    <div className="vote-seg" ref={(el) => { segRefs.current.ghost = el; }} style={{ flex: ingredient.voteData.ghost, background: "var(--ghost)" }} />
                  </div>
                  <div className="vote-pct-row">
                    {(["duck", "heart", "ghost"] as const).map((v) => (
                      <span key={v} className="vote-pct" style={{ color: `var(--${v})`, fontSize: voted === v ? ".78rem" : ".62rem", opacity: voted === v ? 1 : 0.6 }}>
                        {v === "duck" ? "🦆" : v === "heart" ? "❤️" : "👻"} {ingredient.voteData[v]}%
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* INCI Name — large, readable */}
              <div style={{
                fontSize: "1.45rem", fontWeight: 800, color: "#fff",
                letterSpacing: "-.03em", lineHeight: 1.15, marginBottom: 3,
              }}>
                {ingredient.inci}
              </div>

              {/* AKA */}
              <div style={{ fontSize: ".95rem", color: "rgba(255,255,255,.45)", marginBottom: 14 }}>
                AKA &ldquo;<span style={{ color: "rgba(255,255,255,.6)" }}>{ingredient.aka}</span>&rdquo;
              </div>

	<div style={{ fontSize: ".78rem", color: "#aaa", display: "flex", flexDirection: "column", gap: 2 }}>
                <span>{ingredient.type}</span>
                <span>{ingredient.kind}</span>
                <span>{ingredient.origin}</span>
              </div>

              {/* Tap for Facts */}
              <div className="flip-hint" onClick={flipCard} style={{ cursor: "pointer", marginTop: 14 }}>
                Tap ↺ for Facts
              </div>
            </div>
          </div>

          {/* ======= BACK — Ingredient Facts ======= */}
          <div className="card-slide back">
            <div className="back-body">
              <div className="back-title">Ingredient Facts</div>
              <div className="back-rule" />
              <div className="back-product">{ingredient.inci}</div>
              <div className="back-brand">AKA &ldquo;{ingredient.aka}&rdquo;</div>
              <div className="back-meta-row">
                <span>{ingredient.type}</span>
                <span>{ingredient.kind}</span>
                <span>EWG: {ingredient.ewgScore}</span>
              </div>

              {/* Description */}
              <div className="section-line" />
              <div className="section-row">
                <div style={{ fontSize: ".85rem", color: "rgba(255,255,255,.7)", lineHeight: 1.5 }}>
                  {ingredient.description}
                </div>
              </div>

              {/* Science specs */}
              <div className="section-line" />
              <div className="section-row">
                <div className="section-label">
                  Science <span className="section-arrow" style={{ color: "var(--s-ingredients)" }}>▶</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 12px", fontSize: ".8rem" }}>
                  <div><span style={{ color: "rgba(255,255,255,.4)" }}>Effective at </span><span style={{ color: "#fff" }}>{ingredient.concentration}</span></div>
                  <div><span style={{ color: "rgba(255,255,255,.4)" }}>pH </span><span style={{ color: "#fff" }}>{ingredient.ph}</span></div>
                  <div><span style={{ color: "rgba(255,255,255,.4)" }}>Solubility </span><span style={{ color: "#fff" }}>{ingredient.solubility}</span></div>
                  <div><span style={{ color: "rgba(255,255,255,.4)" }}>Comedogenic </span><span style={{ color: "#fff" }}>{ingredient.comedogenicRating}/5</span></div>
                </div>
              </div>

              {/* Functions */}
              <PillSection label="What It Does" color="var(--s-benefits)" pills={ingredient.functions} cardRef={cardRef} wrap />

              {/* Pairs Well */}
              <PillSection label="Pairs Well With" color="var(--clutch)" pills={ingredient.pairsWell} cardRef={cardRef} />

              {/* Avoid With */}
              {ingredient.avoidWith.length > 0 && (
                <PillSection label="Use Caution With" color="var(--heart)" pills={ingredient.avoidWith} cardRef={cardRef} />
              )}

              {/* Regulatory Status */}
              <div className="section-line" />
              <div className="section-row">
                <div className="section-label">
                  Regulatory Status <span className="section-arrow" style={{ color: "var(--s-certs)" }}>▶</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                  {ingredient.regStatus.map((r) => (
                    <div key={r.region} style={{ display: "flex", justifyContent: "space-between", fontSize: ".8rem" }}>
                      <span style={{ color: "rgba(255,255,255,.5)", textTransform: "uppercase", letterSpacing: ".08em" }}>{r.region}</span>
                      <span style={{ color: r.status === "permitted" ? "var(--clutch)" : r.status === "restricted" ? "var(--duck)" : "var(--heart)" }}>
                        {r.status === "permitted" ? "✓" : r.status === "restricted" ? "△" : "✗"} {r.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Found In */}
              <PillSection label="Found In" color="var(--rabbit)" pills={ingredient.foundIn} cardRef={cardRef} seeAll />

              {/* Research Sources */}
              {ingredient.sources.length > 0 && (
                <>
                  <div className="section-line" />
                  <div className="section-row">
                    <div className="section-label">
                      Research <span className="section-arrow" style={{ color: "var(--s-certs)" }}>▶</span>
                    </div>
                    {ingredient.sources.map((s, i) => (
                      <div key={i} style={{ fontSize: ".75rem", color: "rgba(255,255,255,.45)", marginBottom: 3, lineHeight: 1.4 }}>
                        ↗ {s.title} — <em>{s.journal}</em>, {s.year}
                      </div>
                    ))}
                  </div>
                </>
              )}

              <div className="back-verified">Verified {ingredient.verified} · 🧂 = conflict</div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Footer — no Shop button ── */}
      <div className="card-footer">
        <div className="dhg-buttons" style={{ marginBottom: 0 }}>
          {([["duck", "🦆"], ["heart", "❤️"], ["ghost", "👻"]] as const).map(([key, emoji]) => (
            <button key={key} className={`dhg-btn ${key}`} onClick={() => castVote(key)}>
              <div className="dhg-btn-inner">{emoji}</div>
            </button>
          ))}
        </div>
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
