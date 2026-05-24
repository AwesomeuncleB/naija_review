import { useState } from "react";
import TaskA from "./TaskA";
import TaskB from "./TaskB";

const FONTS = `@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,400&display=swap');`;

export default function App() {
  const [tab, setTab] = useState("a");

  return (
    <>
      <style>{FONTS + `
        * { box-sizing: border-box; margin: 0; padding: 0; }
        :root { --accent: #F5A623; --bg: #0a0a0a; --text: #f0ece4; }
        body { background: var(--bg); color: var(--text); font-family: 'DM Sans', sans-serif; }
        @keyframes fadeIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
        @keyframes blink { 0%,100% { opacity:1; } 50% { opacity:0; } }
        select option { background: #1a1a1a; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
      `}</style>

      {/* HEADER */}
      <header style={{
        borderBottom: "1px solid rgba(255,255,255,0.08)",
        padding: "0 1.5rem",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        height: 58, background: "rgba(10,10,10,0.95)",
        backdropFilter: "blur(12px)",
        position: "sticky", top: 0, zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
          <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: "1rem", letterSpacing: "-0.02em" }}>
            Naija<span style={{ color: "#F5A623" }}>Review</span> Intelligence
          </div>

          {/* TABS */}
          <div style={{ display: "flex", gap: 4, background: "#1a1a1a", borderRadius: 8, padding: 3 }}>
            {[
              { id: "a", label: "Task A · User Modeling" },
              { id: "b", label: "Task B · Recommendation" },
            ].map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} style={{
                padding: "5px 14px", borderRadius: 6, border: "none", cursor: "pointer",
                fontFamily: "'DM Sans', sans-serif", fontSize: "0.78rem", fontWeight: 500,
                background: tab === t.id ? "#F5A623" : "transparent",
                color: tab === t.id ? "#000" : "#888",
                transition: "all 0.15s",
              }}>{t.label}</button>
            ))}
          </div>
        </div>

        {/* Status indicator — no key input, backend handles auth */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            fontSize: "0.65rem", padding: "2px 8px", borderRadius: 100,
            background: "rgba(29,185,84,0.1)", color: "#1DB954",
            border: "1px solid rgba(29,185,84,0.3)",
          }}>● API connected</span>
        </div>
      </header>

      {/* CONTENT */}
      {tab === "a" ? <TaskA /> : <TaskB />}
    </>
  );
}
