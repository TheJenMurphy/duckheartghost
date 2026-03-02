"use client";

import { useState, useRef, useCallback } from "react";

/* ── Types ── */
interface PillItem {
  label: string;
  tooltip: string;
}

interface EditorialTag {
  emoji: string;
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
}

export interface Product {
  id: string;
  name: string;
  brand: string;
  price: string;
  pricePerUnit: string;
  category: string;
  type: string;
  galleryImages: string[];
  voteData: { duck: number; heart: number; ghost: number };
  editorialTags: EditorialTag[];
  whatItDoes: PillItem[];
  whoItsFor: PillItem[];
  keyIngredients: PillItem[];
  certifications: PillItem[];
  metaBack: string[];
  verified: string;
}

/* ── Main Card ── */
export default function ProductCard({ product }: { product: Product }) {
  const [flipped, setFlipped] = useState(false);
  const [voted, setVoted] = useState<string | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const segRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const flipCard = () => setFlipped((f) => !f);

  const castVote = (vote: string) => {
    setVoted(vote);
    // glow animation on the winning segment
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
            <button className="nav-btn flip" onClick={flipCard} style={{ fontSize: '1.8rem' }}>
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
          {/* FRONT */}
          <div className="card-slide">
            <div className="gallery-wrapper">
              <div className="gallery">
                {product.galleryImages.map((src, i) => (
                  <div className="gallery-slide" key={i}>
                    <img src={src} alt={`${product.name} ${i + 1}`} className="gallery-img" />
                  </div>
                ))}
              </div>
            </div>
            <div className="front-body">
              {!voted ? (
                <div className="vote-hint">vote to see if the hive agrees</div>
              ) : (
                <div style={{ marginBottom: 8 }}>
                  <div className="vote-bar">
                    <div
                      className="vote-seg"
                      ref={(el) => { segRefs.current.duck = el; }}
                      style={{
                        flex: product.voteData.duck,
                        background: "var(--duck)",
                      }}
                    />
                    <div
                      style={{
                        width: 2,
                        background: "#111",
                        flexShrink: 0,
                      }}
                    />
                    <div
                      className="vote-seg"
                      ref={(el) => { segRefs.current.heart = el; }}
                      style={{
                        flex: product.voteData.heart,
                        background: "var(--heart)",
                      }}
                    />
                    <div
                      style={{
                        width: 2,
                        background: "#111",
                        flexShrink: 0,
                      }}
                    />
                    <div
                      className="vote-seg"
                      ref={(el) => { segRefs.current.ghost = el; }}
                      style={{
                        flex: product.voteData.ghost,
                        background: "var(--ghost)",
                      }}
                    />
                  </div>
                  <div className="vote-pct-row">
                    {(["duck", "heart", "ghost"] as const).map((v) => (
                      <span
                        key={v}
                        className="vote-pct"
                        style={{
                          color: `var(--${v})`,
                          fontSize: voted === v ? ".78rem" : ".62rem",
                          opacity: voted === v ? 1 : 0.6,
                        }}
                      >
                        {v === "duck" ? "🦆" : v === "heart" ? "❤️" : "👻"}{" "}
                        {product.voteData[v]}%
                      </span>
                    ))}
                  </div>
                  <div className="editorial-tags">
                    {product.editorialTags.map((t) => (
                      <span
                        key={t.label}
                        className="etag"
                        style={{
                          background: t.bgColor,
                          color: t.color,
                          border: `1px solid ${t.borderColor}`,
                        }}
                      >
                        {t.emoji} {t.label}
                      </span>
                    ))}
                  </div>
                </div>
              )}
	<div style={{
                fontSize: "1.45rem", fontWeight: 800, color: "#fff",
                letterSpacing: "-.03em", lineHeight: 1.15, marginBottom: 3,
              }}>{product.name}</div>
              <a href={`/brands/${product.brand.toLowerCase().replace(/\s+/g, '-')}`} style={{
                fontSize: ".95rem", color: "var(--rabbit)", fontWeight: 700,
                textDecoration: "none", marginBottom: 4, display: "inline-block",
              }}>{product.brand} →</a>
              <div className="card-meta">
                <span>{product.price}</span>
                <span className="meta-dot" />
                <span>{product.category}</span>
                <span className="meta-dot" />
                <span>{product.type}</span>
              </div>
              <div
                className="flip-hint"
                onClick={flipCard}
                style={{ cursor: "pointer" }}
              >
                Tap ↺ for Product Facts
              </div>
            </div>
          </div>

          {/* BACK */}
          <div className="card-slide back">
            <div className="back-body">
              <div className="back-title">Product Facts</div>
              <div className="back-rule" />
              <div className="back-product">{product.name}</div>
              <div className="back-brand">{product.brand}</div>
              <div className="back-meta-row">
                {product.metaBack.map((m, i) => (
                  <span key={i}>{m}</span>
                ))}
              </div>

              <PillSection
                label="What It Does"
                color="var(--s-benefits)"
                pills={product.whatItDoes}
                cardRef={cardRef}
                wrap
              />
              <PillSection
                label="Who It's For"
                color="var(--s-who)"
                pills={product.whoItsFor}
                cardRef={cardRef}
              />
              <PillSection
                label="What It Is"
                color="var(--s-ingredients)"
                pills={product.keyIngredients}
                cardRef={cardRef}
                seeAll
              />
              <PillSection
                label="Certifications &amp; Safety"
                color="var(--s-certs)"
                pills={product.certifications}
                cardRef={cardRef}
              />

              <div className="section-line" />
              <div className="back-price">
                <span className="price-big">{product.price}</span>
                <span className="price-per">{product.pricePerUnit}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Footer ── */}
      <div className="card-footer">
        <div className="dhg-buttons">
          {(
            [
              ["duck", "🦆"],
              ["heart", "❤️"],
              ["ghost", "👻"],
            ] as const
          ).map(([key, emoji]) => (
            <button
              key={key}
              className={`dhg-btn ${key}`}
              onClick={() => castVote(key)}
            >
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
  label,
  color,
  pills,
  cardRef,
  wrap,
  seeAll,
}: {
  label: string;
  color: string;
  pills: PillItem[];
  cardRef: React.RefObject<HTMLDivElement | null>;
  wrap?: boolean;
  seeAll?: boolean;
}) {
  return (
    <>
      <div className="section-line" />
      <div className="section-row">
        <div className="section-label">
          {label}{" "}
          <span className="section-arrow" style={{ color }}>
            ▶
          </span>
        </div>
        <div className={`pill-row${wrap ? " wrap" : ""}`}>
          {pills.map((p) => (
            <Tooltip
              key={p.label}
              label={p.label}
              tooltip={p.tooltip}
              color={color}
              cardRef={cardRef}
            />
          ))}
        </div>
        {seeAll && (
          <a href="#" className="see-all">
            See all ingredients →
          </a>
        )}
      </div>
    </>
  );
}

/* ── Tooltip Pill ── */
function Tooltip({
  label,
  tooltip,
  color,
  cardRef,
}: {
  label: string;
  tooltip: string;
  color: string;
  cardRef: React.RefObject<HTMLDivElement | null>;
}) {
  const tipRef = useRef<HTMLSpanElement>(null);

  const handleMouseEnter = useCallback(() => {
    const box = tipRef.current?.querySelector(".tipbox") as HTMLElement | null;
    if (!box || !cardRef.current) return;
    box.style.left = "0";
    box.style.right = "auto";
    const rect = box.getBoundingClientRect();
    const cardRect = cardRef.current.getBoundingClientRect();
    if (rect.right > cardRect.right - 8) {
      box.style.left = "auto";
      box.style.right = "0";
    }
    if (rect.left < cardRect.left + 8) {
      box.style.left = "0";
      box.style.right = "auto";
    }
  }, [cardRef]);

  return (
    <span className="tip" ref={tipRef} onMouseEnter={handleMouseEnter}>
      <span className="pill" style={{ "--c": color } as React.CSSProperties}>
        {label}
      </span>
      <span className="tipbox">
        <div className="tipbox-term">{label}</div>
        <div className="tipbox-body">{tooltip}</div>
      </span>
    </span>
  );
}
