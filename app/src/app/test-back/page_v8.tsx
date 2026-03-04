"use client";
import ProductFactsBack from "../../components/ProductFactsBack";

export default function TestBackPage() {
  return (
    <div style={{
      minHeight: "100dvh",
      background: "#1a1a1c",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "20px",
    }}>
      {/* Rainbow bar at top like the real card header */}
      <div style={{
        width: "100%",
        maxWidth: 380,
        borderRadius: 16,
        overflow: "hidden",
        boxShadow: "0 20px 60px rgba(0,0,0,.6)",
      }}>
        {/* Fake card header */}
        <div style={{
          background: "rgba(40,40,44,.85)",
          backdropFilter: "blur(40px)",
        }}>
          <div style={{
            height: 5,
            background: "linear-gradient(90deg, #ffaa00 0%, #ffaa00 3%, #ff8c2a 11%, #ff5533 22%, #ff4466 31%, #ff4d8a 40%, #d946ef 52%, #9955ff 64%, #3399ff 75%, #44ddee 87%, #00c4b0 100%)",
          }} />
          <div style={{
            height: 42,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 20px",
          }}>
            <span style={{ color: "rgba(255,255,255,.5)", fontSize: 13 }}>↺ ← flip</span>
            <span style={{
              fontFamily: "'Space Mono', monospace",
              fontSize: ".6rem",
              color: "rgba(255,255,255,.3)",
              textTransform: "uppercase",
              letterSpacing: ".1em",
            }}>
              test-back preview
            </span>
            <span style={{ color: "rgba(255,255,255,.5)", fontSize: 13 }}>🐇 🔍</span>
          </div>
        </div>

        {/* The actual component */}
        <ProductFactsBack onFlipBack={() => alert("flip back!")} />

        {/* Fake card footer */}
        <div style={{
          background: "rgba(40,40,44,.85)",
          backdropFilter: "blur(40px)",
          padding: "12px 20px 16px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 12,
          borderRadius: "0 0 16px 16px",
        }}>
          {/* Row 1: Vote buttons */}
          <div style={{ display: "flex", justifyContent: "center", gap: 16 }}>
            {[
              { emoji: "🦆", color: "#ffaa00" },
              { emoji: "❤️", color: "#ff4466" },
              { emoji: "👻", color: "#9955ff" },
            ].map(({ emoji, color }) => (
              <button key={emoji} style={{
                width: 52,
                height: 52,
                borderRadius: "50%",
                background: "#000",
                border: `2px solid ${color}`,
                fontSize: "1.35rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}>
                {emoji}
              </button>
            ))}
          </div>
          {/* Row 2: Shop & Support — rainbow border + gradient text */}
          <div style={{
            width: "100%",
            padding: 2,
            borderRadius: 9999,
            background: "linear-gradient(90deg, #ffaa00 0%, #ff8c2a 11%, #ff5533 22%, #ff4466 31%, #ff4d8a 40%, #d946ef 52%, #9955ff 64%, #3399ff 75%, #44ddee 87%, #00c4b0 100%)",
          }}>
            <button style={{
              width: "100%",
              padding: "12px 0",
              borderRadius: 9999,
              background: "#000",
              border: "none",
              fontSize: ".9rem",
              fontWeight: 700,
              fontFamily: "'Outfit', sans-serif",
              cursor: "pointer",
              letterSpacing: ".03em",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}>
              <span style={{
                backgroundImage: "linear-gradient(90deg, #ffaa00 0%, #ff8c2a 11%, #ff5533 22%, #ff4466 31%, #ff4d8a 40%, #d946ef 52%, #9955ff 64%, #3399ff 75%, #44ddee 87%, #00c4b0 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}>
                🛍️ Shop &amp; Support
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
