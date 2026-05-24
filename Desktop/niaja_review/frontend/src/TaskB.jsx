import { useState, useRef } from "react";

const NAIJA_CITIES = ["Lagos", "Abuja", "Port Harcourt", "Kano", "Ibadan", "Benin City", "Enugu", "Kaduna"];
const CATEGORIES   = ["Restaurants", "Hotels", "Shopping", "Electronics", "Beauty", "Entertainment", "Transport", "Books"];
const NAIJA_TRAITS = ["Budget-conscious", "Quality-first", "Trendy", "Traditional", "Abroad returnee", "Lagos hustler", "Family-oriented", "Young professional"];

const STAR_COLORS = ["", "#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#27ae60"];

// No apiKey prop — backend reads key from its own .env
export default function TaskB() {
  const [persona, setPersona] = useState({
    userId: "",
    city: "Lagos",
    traits: ["Budget-conscious"],
    category: "Restaurants",
    age: "25",
    occupation: "Tech worker",
  });
  const [conversation, setConversation]       = useState([]);
  const [inputMsg, setInputMsg]               = useState("");
  const [loading, setLoading]                 = useState(false);
  const [streamText, setStreamText]           = useState("");
  const [recommendations, setRecommendations] = useState([]);
  const [reasoningTrace, setReasoningTrace]   = useState("");
  const [coldStartQs, setColdStartQs]         = useState([]);
  const [mode, setMode]                       = useState("setup"); // setup | chat
  const chatRef = useRef(null);

  const toggleTrait = (t) => {
    setPersona(p => ({
      ...p,
      traits: p.traits.includes(t) ? p.traits.filter(x => x !== t) : [...p.traits, t],
    }));
  };

  const callBackend = async (messages) => {
    setLoading(true);
    setStreamText("");

    // No api_key field — backend uses ANTHROPIC_API_KEY from .env
    const body = {
      manual_persona: {
        avg_stars: 3.5,
        review_count: 0,
        style_fingerprint: {
          dominant_topic: persona.category,
          avg_rating: 3.5,
          tone: "balanced",
          avg_words_per_review: 60,
        },
      },
      city: persona.city,
      naija_traits: persona.traits,
      category_hint: persona.category,
      conversation_history: messages,
    };

    try {
      const res = await fetch("http://localhost:8000/task-b/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let fullText  = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        for (const line of chunk.split("\n")) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6).trim();
            if (data === "[DONE]") continue;
            try {
              const parsed = JSON.parse(data);
              if (parsed.type === "content_block_delta" && parsed.delta?.text) {
                fullText += parsed.delta.text;
                setStreamText(fullText);
              }
            } catch {}
          }
        }
      }

      const clean = fullText.replace(/```json|```/g, "").trim();
      try {
        const result = JSON.parse(clean);
        setRecommendations(result.recommendations || []);
        setReasoningTrace(result.reasoning_trace || "");
        setColdStartQs(result.cold_start_questions || []);

        const assistantMsg = { role: "assistant", content: fullText, parsed: result };
        setConversation(prev => [...prev, assistantMsg]);
      } catch {}
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
      setStreamText("");
    }
  };

  const startChat = () => {
    setMode("chat");
    setConversation([]);
    setRecommendations([]);
    callBackend([{
      role: "user",
      content: `Recommend ${persona.category} for me. I am ${persona.age}, ${persona.occupation}, based in ${persona.city}. My traits: ${persona.traits.join(", ")}.`,
    }]);
  };

  const sendMessage = () => {
    if (!inputMsg.trim() || loading) return;
    const userMsg  = { role: "user", content: inputMsg };
    const newConvo = [...conversation, userMsg];
    setConversation(newConvo);
    setInputMsg("");
    callBackend(newConvo.map(m => ({ role: m.role, content: m.content })));
  };

  const RecommendationCard = ({ rec, index }) => (
    <div style={{
      background: "#141414",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: 12,
      padding: "1.25rem",
      marginBottom: "0.875rem",
      animation: "fadeIn 0.4s ease",
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "0.75rem" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{
              background: "#F5A623", color: "#000",
              fontFamily: "'Syne', sans-serif", fontWeight: 700,
              fontSize: "0.72rem", padding: "2px 8px", borderRadius: 100,
            }}>#{rec.rank || index + 1}</span>
            <span style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: "1rem" }}>{rec.name}</span>
          </div>
          <div style={{ fontSize: "0.78rem", color: "#888", marginTop: 3 }}>{rec.business_id}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "1.1rem", fontWeight: 700, color: STAR_COLORS[Math.round(rec.predicted_rating)] || "#F5A623" }}>
            ★ {rec.predicted_rating?.toFixed(1)}
          </div>
          <div style={{ fontSize: "0.7rem", color: "#666" }}>{Math.round((rec.confidence || 0.7) * 100)}% match</div>
        </div>
      </div>

      <div style={{
        fontSize: "0.875rem", lineHeight: 1.7, color: "#d4cfc7",
        padding: "0.875rem", background: "#1a1a1a",
        borderRadius: 8, borderLeft: "3px solid #F5A623",
        marginBottom: "0.75rem",
      }}>
        {rec.reason}
      </div>

      {rec.naija_note && (
        <div style={{
          fontSize: "0.78rem", color: "#F5A623",
          background: "rgba(245,166,35,0.07)",
          border: "1px solid rgba(245,166,35,0.2)",
          borderRadius: 6, padding: "0.5rem 0.75rem",
        }}>
          🇳🇬 {rec.naija_note}
        </div>
      )}
    </div>
  );

  return (
    <div style={{ display: "grid", gridTemplateColumns: mode === "setup" ? "1fr" : "360px 1fr", minHeight: "calc(100vh - 60px)", fontFamily: "'DM Sans', sans-serif" }}>
      {/* SETUP PANEL */}
      {mode === "setup" ? (
        <div style={{ maxWidth: 560, margin: "0 auto", padding: "2rem 1rem", width: "100%" }}>
          <div style={{ marginBottom: "2rem" }}>
            <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: "1.6rem", marginBottom: "0.5rem" }}>
              Task B — <span style={{ color: "#F5A623" }}>Recommendation</span>
            </div>
            <div style={{ color: "#888", fontSize: "0.875rem" }}>
              Configure a Nigerian user persona. The agent will reason through candidates and recommend the best matches.
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.875rem", marginBottom: "1rem" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", color: "#888", marginBottom: 4 }}>City</label>
              <select value={persona.city} onChange={e => setPersona(p => ({...p, city: e.target.value}))} style={selectStyle}>
                {NAIJA_CITIES.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", color: "#888", marginBottom: 4 }}>Age</label>
              <input value={persona.age} onChange={e => setPersona(p => ({...p, age: e.target.value}))} style={inputStyle} />
            </div>
          </div>

          <div style={{ marginBottom: "1rem" }}>
            <label style={{ display: "block", fontSize: "0.78rem", color: "#888", marginBottom: 4 }}>Occupation</label>
            <input value={persona.occupation} onChange={e => setPersona(p => ({...p, occupation: e.target.value}))} style={inputStyle} placeholder="e.g. banker, student, trader..." />
          </div>

          <div style={{ marginBottom: "1rem" }}>
            <label style={{ display: "block", fontSize: "0.78rem", color: "#888", marginBottom: 4 }}>What to Recommend</label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {CATEGORIES.map(c => (
                <button key={c} onClick={() => setPersona(p => ({...p, category: c}))}
                  style={{ ...tagStyle, ...(persona.category === c ? tagActiveStyle : {}) }}>
                  {c}
                </button>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: "1.5rem" }}>
            <label style={{ display: "block", fontSize: "0.78rem", color: "#888", marginBottom: 4 }}>User Traits</label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {NAIJA_TRAITS.map(t => (
                <button key={t} onClick={() => toggleTrait(t)}
                  style={{ ...tagStyle, ...(persona.traits.includes(t) ? tagActiveStyle : {}) }}>
                  {t}
                </button>
              ))}
            </div>
          </div>

          <button onClick={startChat} style={btnStyle}>
            Start Recommendation Session →
          </button>
        </div>
      ) : (
        <>
          {/* CONVERSATION SIDEBAR */}
          <div style={{ borderRight: "1px solid rgba(255,255,255,0.08)", padding: "1.25rem", background: "#111", overflowY: "auto", maxHeight: "calc(100vh - 60px)" }}>
            <button onClick={() => { setMode("setup"); setConversation([]); setRecommendations([]); }}
              style={{ fontSize: "0.78rem", color: "#888", background: "none", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 6, padding: "4px 10px", cursor: "pointer", marginBottom: "1rem" }}>
              ← New Session
            </button>

            <div style={{ fontSize: "0.65rem", letterSpacing: "0.15em", textTransform: "uppercase", color: "#555", marginBottom: "0.75rem" }}>Persona</div>
            <div style={{ background: "#1a1a1a", borderRadius: 10, padding: "0.875rem", marginBottom: "1rem" }}>
              <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, marginBottom: 4 }}>{persona.age}yo · {persona.city}</div>
              <div style={{ fontSize: "0.78rem", color: "#888" }}>{persona.occupation}</div>
              <div style={{ fontSize: "0.72rem", color: "#F5A623", marginTop: 4 }}>{persona.traits.join(" · ")}</div>
            </div>

            <div style={{ fontSize: "0.65rem", letterSpacing: "0.15em", textTransform: "uppercase", color: "#555", marginBottom: "0.75rem" }}>Conversation</div>

            <div style={{ marginBottom: "1rem" }}>
              {conversation.map((msg, i) => (
                <div key={i} style={{
                  fontSize: "0.8rem", marginBottom: "0.75rem",
                  padding: "0.625rem 0.75rem",
                  background: msg.role === "user" ? "rgba(245,166,35,0.08)" : "#1a1a1a",
                  borderRadius: 8,
                  borderLeft: `2px solid ${msg.role === "user" ? "#F5A623" : "rgba(255,255,255,0.1)"}`,
                  color: msg.role === "user" ? "#f0ece4" : "#888",
                }}>
                  <div style={{ fontSize: "0.65rem", color: "#555", marginBottom: 2, textTransform: "uppercase", letterSpacing: "0.1em" }}>
                    {msg.role === "user" ? "You" : "Agent"}
                  </div>
                  {msg.role === "user" ? msg.content : `Returned ${msg.parsed?.recommendations?.length || 0} recommendations`}
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: 6 }}>
              <input
                value={inputMsg}
                onChange={e => setInputMsg(e.target.value)}
                onKeyDown={e => e.key === "Enter" && sendMessage()}
                placeholder="Refine... e.g. cheaper options?"
                style={{ ...inputStyle, flex: 1, fontSize: "0.8rem" }}
              />
              <button onClick={sendMessage} disabled={loading} style={{ ...btnStyle, padding: "0.5rem 0.875rem", fontSize: "0.8rem" }}>→</button>
            </div>

            {coldStartQs.length > 0 && (
              <div style={{ marginTop: "0.875rem" }}>
                <div style={{ fontSize: "0.7rem", color: "#F5A623", marginBottom: 4 }}>Agent wants to know:</div>
                {coldStartQs.map((q, i) => (
                  <button key={i} onClick={() => setInputMsg(q)}
                    style={{ display: "block", width: "100%", textAlign: "left", fontSize: "0.78rem", padding: "0.5rem 0.75rem", background: "rgba(245,166,35,0.06)", border: "1px solid rgba(245,166,35,0.2)", borderRadius: 8, color: "#d4cfc7", cursor: "pointer", marginBottom: 4 }}>
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* RECOMMENDATIONS PANEL */}
          <div style={{ padding: "1.5rem", overflowY: "auto", maxHeight: "calc(100vh - 60px)" }} ref={chatRef}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem" }}>
              <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: "1.3rem" }}>
                Recommendations
              </div>
              {recommendations.length > 0 && (
                <span style={{ fontSize: "0.78rem", color: "#888" }}>{recommendations.length} matched</span>
              )}
            </div>

            {loading && (
              <div style={{ background: "#141414", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: "1.25rem", marginBottom: "0.875rem" }}>
                <div style={{ fontSize: "0.875rem", color: "#d4cfc7", padding: "0.875rem", background: "#1a1a1a", borderRadius: 8, borderLeft: "3px solid #F5A623", minHeight: 80, whiteSpace: "pre-wrap" }}>
                  {streamText || "Agent is reasoning through candidates..."}
                  <span style={{ display: "inline-block", width: 2, height: "1em", background: "#F5A623", marginLeft: 2, animation: "blink 0.7s infinite", verticalAlign: "text-bottom" }} />
                </div>
              </div>
            )}

            {!loading && recommendations.length === 0 && (
              <div style={{ textAlign: "center", padding: "4rem 2rem", color: "#555" }}>
                <div style={{ fontSize: "2.5rem", marginBottom: "1rem" }}>🤔</div>
                <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, marginBottom: "0.5rem" }}>Agent is thinking...</div>
                <div style={{ fontSize: "0.875rem" }}>Recommendations will appear here once the agent responds.</div>
              </div>
            )}

            {recommendations.map((rec, i) => <RecommendationCard key={rec.business_id || i} rec={rec} index={i} />)}

            {reasoningTrace && (
              <div style={{ marginTop: "1rem", padding: "1rem", background: "#0d0d0d", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 10 }}>
                <div style={{ fontSize: "0.65rem", letterSpacing: "0.15em", textTransform: "uppercase", color: "#555", marginBottom: "0.5rem" }}>Agent Reasoning Trace</div>
                <div style={{ fontSize: "0.8rem", color: "#666", lineHeight: 1.7 }}>{reasoningTrace}</div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ── Inline styles ─────────────────────────────────────────────────────────────
const inputStyle = {
  width: "100%", background: "#1a1a1a", border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 8, color: "#f0ece4", fontFamily: "'DM Sans', sans-serif",
  fontSize: "0.875rem", padding: "0.6rem 0.85rem", outline: "none",
};
const selectStyle = { ...inputStyle };
const tagStyle = {
  fontSize: "0.75rem", padding: "4px 10px", borderRadius: 100,
  border: "1px solid rgba(255,255,255,0.08)", cursor: "pointer",
  background: "transparent", color: "#888", fontFamily: "'DM Sans', sans-serif",
  transition: "all 0.15s",
};
const tagActiveStyle = { background: "#F5A623", borderColor: "#F5A623", color: "#000", fontWeight: 500 };
const btnStyle = {
  width: "100%", padding: "0.85rem", background: "#F5A623", color: "#000",
  fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: "0.9rem",
  border: "none", borderRadius: 10, cursor: "pointer",
};
