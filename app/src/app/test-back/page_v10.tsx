"use client";
import ProductFactsBack from "../../components/ProductFactsBack";

export default function TestBackPage() {
  return (
    <div style={{
      height: "100dvh",
      background: "#1a1a1c",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "20px",
    }}>
      <div style={{
        width: "100%",
        maxWidth: 380,
        height: "100%",
        maxHeight: "820px",
        borderRadius: 16,
        overflow: "hidden",
        boxShadow: "0 20px 60px rgba(0,0,0,.6)",
        display: "flex",
        flexDirection: "column",
      }}>
        {/* Card header — fixed */}
        <div className="card-header" style={{ flexShrink: 0 }}>
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

        {/* Scrollable middle */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          overflowX: "hidden",
          WebkitOverflowScrolling: "touch",
        }}>
          <ProductFactsBack onFlipBack={() => alert("flip back!")} />
        </div>

        {/* Card footer — fixed */}
        <div className="card-footer" style={{ flexShrink: 0 }}>
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
