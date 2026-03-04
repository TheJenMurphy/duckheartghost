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
      <div style={{
        width: "100%",
        maxWidth: 380,
        borderRadius: 16,
        overflow: "hidden",
        boxShadow: "0 20px 60px rgba(0,0,0,.6)",
      }}>
        {/* Card header — same as ProductCard */}
        <div className="card-header">
          <div className="site-header-inner">
            <div className="rainbow-bar" />
            <div className="nav-inner">
              <button className="nav-btn flip" style={{ fontSize: '1.8rem' }}>⟲</button>
              <button className="nav-btn">🐇</button>
              <button className="nav-btn">🪞</button>
              <button className="nav-btn">🔍</button>
              <button className="nav-btn active">❤️</button>
            </div>
          </div>
        </div>

        {/* The card back filling */}
        <ProductFactsBack onFlipBack={() => alert("flip back!")} />

        {/* Card footer — same as ProductCard */}
        <div className="card-footer">
          <div className="dhg-buttons">
            <button className="dhg-btn duck"><div className="dhg-btn-inner">🦆</div></button>
            <button className="dhg-btn heart"><div className="dhg-btn-inner">❤️</div></button>
            <button className="dhg-btn ghost"><div className="dhg-btn-inner">👻</div></button>
          </div>
          <button className="shop-btn">
            <div className="shop-btn-inner">
              <span>👜</span>
              <span className="shop-label">Shop &amp; Support</span>
            </div>
          </button>
        </div>

      </div>
    </div>
  );
}
