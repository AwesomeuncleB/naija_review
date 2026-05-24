import { useState, useEffect, useRef } from "react";

const API = "http://localhost:8000";
const NAIJA_CITIES  = ["Lagos","Abuja","Port Harcourt","Kano","Ibadan","Benin City","Enugu","Kaduna"];
const NAIJA_CONTEXT = ["Speaks Pidgin","Brand-loyal","Bargain hunter","Quality-first","Lagos hustler","Abroad returnee"];
const PIDGIN_LEVELS = ["none","low","medium","high"];

export default function TaskA() {
  const [mode, setMode]           = useState("real");
  const [users, setUsers]         = useState([]);
  const [selectedUser, setUser]   = useState(null);
  const [businesses, setBiz]      = useState([]);
  const [selectedBiz, setBizSel]  = useState(null);
  const [bizSearch, setBizSearch] = useState("");
  const [city, setCity]           = useState("Lagos");
  const [naijaTraits, setTraits]  = useState(["Speaks Pidgin","Price-conscious"]);
  const [pidginLevel, setPidgin]  = useState("medium");
  const [manualBiz, setManualBiz] = useState({ name: "", category: "Restaurant / Food", description: "" });
  const [results, setResults]     = useState([]);
  const [loading, setLoading]     = useState(false);
  const [streamText, setStream]   = useState("");
  const [loadingUsers, setLU]     = useState(false);
  const outputRef = useRef(null);

  useEffect(() => {
    setLU(true);
    fetch(`${API}/users?min_reviews=20&limit=20`)
      .then(r => r.json())
      .then(d => { setUsers(d.users || []); setLU(false); })
      .catch(() => setLU(false));
  }, []);

  useEffect(() => {
    if (bizSearch.length < 2) return;
    const t = setTimeout(() => {
      fetch(`${API}/businesses?search=${encodeURIComponent(bizSearch)}&limit=8`)
        .then(r => r.json())
        .then(d => setBiz(d.businesses || []));
    }, 300);
    return () => clearTimeout(t);
  }, [bizSearch]);

  const toggleTrait = (t) =>
    setTraits(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]);

  const parseResponse = (full) => {
    let clean = full.replace(/```json/g, "").replace(/```/g, "").trim();
    try { return JSON.parse(clean); } catch {}
    const lastBrace = clean.lastIndexOf("}");
    if (lastBrace > 0) {
      try { return JSON.parse(clean.slice(0, lastBrace + 1)); } catch {}
    }
    const reviewMatch = clean.match(/"review"\s*:\s*"([\s\S]*?)(?<!\\)"/);
    const ratingMatch = clean.match(/"rating"\s*:\s*(\d)/);
    if (reviewMatch) {
      return {
        rating: ratingMatch ? parseInt(ratingMatch[1]) : 3,
        review: reviewMatch[1].replace(/\\n/g, "\n").replace(/\\"/g, '"'),
        tone: "balanced", key_praises: [], key_complaints: [],
        behavioral_notes: "(response was partially truncated)",
      };
    }
    return null;
  };

  const generate = async () => {
    if (mode === "real" && (!selectedUser || !selectedBiz)) return;
    if (mode === "manual" && !manualBiz.name.trim()) return;
    setLoading(true); setStream("");

    const body = mode === "real"
      ? { user_id: selectedUser.user_id, business_id: selectedBiz.business_id, city, naija_traits: naijaTraits, pidgin_level: pidginLevel }
      : {
          manual_persona: { avg_stars: 3.5, review_count: 20, style_fingerprint: { avg_rating: 3.5, dominant_topic: "food", tone: "balanced", avg_words_per_review: 80 } },
          manual_business: { name: manualBiz.name, categories: manualBiz.category, city, stars: 3.8, review_count: 100, attributes: {} },
          city, naija_traits: naijaTraits, pidgin_level: pidginLevel,
        };

    try {
      const res = await fetch(`${API}/task-a/generate`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const reader = res.body.getReader();
      const dec    = new TextDecoder();
      let full     = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const line of dec.decode(value).split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const p = JSON.parse(line.slice(6));
            if (p.type === "content_block_delta" && p.delta?.text) {
              full += p.delta.text; setStream(full);
            }
          } catch {}
        }
      }
      const parsed = parseResponse(full);
      if (parsed) {
        setResults(prev => [{
          id: Date.now(),
          user: selectedUser || { user_id: "manual", avg_stars: 3.5 },
          biz:  selectedBiz  || { name: manualBiz.name, categories: manualBiz.category },
          ...parsed,
        }, ...prev]);
      } else {
        console.error("Could not parse response:", full);
      }
    } catch(e) { console.error(e); }
    finally { setLoading(false); setStream(""); }
  };

  const canGenerate = !loading && (mode === "real" ? (selectedUser && selectedBiz) : manualBiz.name.trim());

  return (
    <div style={{ display:"grid", gridTemplateColumns:"380px 1fr", minHeight:"calc(100vh - 58px)" }}>
      <aside style={{ borderRight:"1px solid rgba(255,255,255,0.08)", padding:"1.5rem", overflowY:"auto", maxHeight:"calc(100vh - 58px)", background:"#111" }}>

        <div style={{ display:"flex", gap:4, background:"#1a1a1a", borderRadius:8, padding:3, marginBottom:"1.25rem" }}>
          {[["real","🗄 Real Yelp User"],["manual","✏️ Manual Persona"]].map(([id,label]) => (
            <button key={id} onClick={() => setMode(id)} style={{
              flex:1, padding:"6px 0", borderRadius:6, border:"none", cursor:"pointer",
              fontSize:"0.75rem", fontWeight:500, fontFamily:"'DM Sans',sans-serif",
              background: mode===id ? "#F5A623" : "transparent",
              color: mode===id ? "#000" : "#666", transition:"all 0.15s",
            }}>{label}</button>
          ))}
        </div>

        {mode === "real" ? (<>
          <SectionLabel>Select a Real User</SectionLabel>
          {loadingUsers
            ? <div style={{color:"#555",fontSize:"0.8rem"}}>Loading users from DB...</div>
            : <div style={{display:"flex",flexDirection:"column",gap:6,marginBottom:"1rem"}}>
                {users.map(u => (
                  <button key={u.user_id} onClick={() => setUser(u)} style={{
                    textAlign:"left", padding:"0.6rem 0.875rem", borderRadius:8, cursor:"pointer",
                    border: selectedUser?.user_id===u.user_id ? "1px solid #F5A623" : "1px solid rgba(255,255,255,0.08)",
                    background: selectedUser?.user_id===u.user_id ? "rgba(245,166,35,0.08)" : "#1a1a1a",
                    color:"#f0ece4",
                  }}>
                    <div style={{fontSize:"0.78rem",fontWeight:600,fontFamily:"'DM Sans',sans-serif"}}>{u.user_id.slice(0,14)}…</div>
                    <div style={{fontSize:"0.7rem",color:"#888",marginTop:2}}>
                      {u.review_count.toLocaleString()} reviews · ★ {u.avg_stars?.toFixed(1)} avg · {u.style_fingerprint?.tone || "–"} tone
                    </div>
                  </button>
                ))}
              </div>
          }
          <SectionLabel>Search a Business</SectionLabel>
          <input value={bizSearch} onChange={e => setBizSearch(e.target.value)} placeholder="Search restaurant, hotel, shop..." style={inp} />
          {businesses.length > 0 && (
            <div style={{marginTop:6,display:"flex",flexDirection:"column",gap:4}}>
              {businesses.map(b => (
                <button key={b.business_id} onClick={() => { setBizSel(b); setBiz([]); setBizSearch(b.name); }} style={{
                  textAlign:"left", padding:"0.5rem 0.75rem", borderRadius:8, cursor:"pointer",
                  border: selectedBiz?.business_id===b.business_id ? "1px solid #F5A623" : "1px solid rgba(255,255,255,0.08)",
                  background: selectedBiz?.business_id===b.business_id ? "rgba(245,166,35,0.08)" : "#1a1a1a",
                  color:"#f0ece4",
                }}>
                  <div style={{fontSize:"0.78rem",fontWeight:600}}>{b.name}</div>
                  <div style={{fontSize:"0.7rem",color:"#888"}}>{b.city} · ★{b.stars} · {b.categories?.split(",")[0]}</div>
                </button>
              ))}
            </div>
          )}
        </>) : (<>
          <SectionLabel>Business to Review</SectionLabel>
          <Field label="Business / Product Name">
            <input value={manualBiz.name} onChange={e => setManualBiz(p=>({...p,name:e.target.value}))} style={inp} placeholder="e.g. Mr Biggs, Shoprite..." />
          </Field>
          <Field label="Category">
            <select value={manualBiz.category} onChange={e => setManualBiz(p=>({...p,category:e.target.value}))} style={inp}>
              {["Restaurant / Food","Electronics","Fashion","Hotel","Retail","Books","Beauty","Transport"].map(c=><option key={c}>{c}</option>)}
            </select>
          </Field>
        </>)}

        <hr style={{border:"none",borderTop:"1px solid rgba(255,255,255,0.06)",margin:"1.25rem 0"}} />
        <SectionLabel>Nigerian Context</SectionLabel>
        <Field label="City">
          <select value={city} onChange={e => setCity(e.target.value)} style={inp}>
            {NAIJA_CITIES.map(c=><option key={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Cultural Traits">
          <div style={{display:"flex",flexWrap:"wrap",gap:5,marginTop:4}}>
            {NAIJA_CONTEXT.map(t=>(
              <button key={t} onClick={()=>toggleTrait(t)} style={{...tagStyle,...(naijaTraits.includes(t)?tagActive:{})}}>
                {t}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Pidgin Intensity">
          <div style={{display:"flex",gap:6}}>
            {PIDGIN_LEVELS.map(l=>(
              <button key={l} onClick={()=>setPidgin(l)} style={{...tagStyle,...(pidginLevel===l?tagActive:{})}}>
                {l}
              </button>
            ))}
          </div>
        </Field>
        <button onClick={generate} disabled={!canGenerate} style={{
          ...btnStyle, opacity: canGenerate ? 1 : 0.4, cursor: canGenerate ? "pointer" : "not-allowed"
        }}>
          {loading ? "Generating..." : "Generate Review →"}
        </button>
        {mode==="real" && !selectedUser && <div style={{fontSize:"0.72rem",color:"#888",marginTop:4,textAlign:"center"}}>Select a user above</div>}
        {mode==="real" && selectedUser && !selectedBiz && <div style={{fontSize:"0.72rem",color:"#888",marginTop:4,textAlign:"center"}}>Search and select a business</div>}
      </aside>

      <main style={{padding:"1.5rem",overflowY:"auto",maxHeight:"calc(100vh - 58px)"}} ref={outputRef}>
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:"1.5rem"}}>
          <div style={{fontFamily:"'Syne',sans-serif",fontWeight:700,fontSize:"1.3rem"}}>Generated Reviews</div>
          {results.length > 0 && <span style={{fontSize:"0.78rem",color:"#888"}}>{results.length} result{results.length>1?"s":""}</span>}
        </div>

        {loading && (
          <div style={cardStyle}>
            <div style={{background:"#1a1a1a",borderRadius:8,borderLeft:"3px solid #F5A623",padding:"1rem",minHeight:80,fontSize:"0.875rem",lineHeight:1.7,color:"#d4cfc7",whiteSpace:"pre-wrap"}}>
              {streamText || "Analysing user behaviour..."}
              <span style={{display:"inline-block",width:2,height:"1em",background:"#F5A623",marginLeft:2,animation:"blink 0.7s infinite",verticalAlign:"text-bottom"}} />
            </div>
          </div>
        )}

        {!loading && results.length === 0 && (
          <div style={{textAlign:"center",padding:"5rem 2rem",color:"#555"}}>
            <div style={{fontSize:"3rem",marginBottom:"1rem"}}>🇳🇬</div>
            <div style={{fontFamily:"'Syne',sans-serif",fontWeight:700,fontSize:"1.1rem",marginBottom:"0.5rem",color:"#888"}}>Ready to generate</div>
            <div style={{fontSize:"0.875rem"}}>{mode==="real" ? "Pick a user and a business from the DB, then hit Generate." : "Enter a business name and hit Generate."}</div>
          </div>
        )}

        {results.map(r => (
          <div key={r.id} style={{...cardStyle,animation:"fadeIn 0.4s ease"}}>
            <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:"1rem"}}>
              <div>
                <div style={{fontFamily:"'Syne',sans-serif",fontWeight:700,fontSize:"1.05rem"}}>{r.biz?.name}</div>
                <div style={{fontSize:"0.75rem",color:"#888",marginTop:2}}>{r.biz?.categories?.split(",")[0]} · {r.biz?.city || city}</div>
              </div>
              <div style={{textAlign:"right",flexShrink:0}}>
                <div style={{fontFamily:"'Syne',sans-serif",fontWeight:700,color:"#F5A623",fontSize:"1.4rem"}}>★ {r.rating}/5</div>
                <div style={{fontSize:"0.7rem",color:"#888"}}>predicted</div>
              </div>
            </div>
            <div style={{background:"#1a1a1a",borderRadius:8,borderLeft:"3px solid #F5A623",padding:"1rem",marginBottom:"0.875rem",fontSize:"0.875rem",lineHeight:1.75,color:"#d4cfc7"}}>
              {r.review}
            </div>
            <div style={{display:"flex",flexWrap:"wrap",gap:6,marginBottom:"0.75rem"}}>
              {r.tone && <Pill label={`Tone: ${r.tone}`} />}
              {r.pidgin_intensity && <Pill label={`Pidgin: ${r.pidgin_intensity}`} color="#F5A623" />}
              {r.key_praises?.slice(0,3).map((p,i)=><Pill key={i} label={`✓ ${p}`} color="#1DB954" />)}
              {r.key_complaints?.slice(0,2).map((c,i)=><Pill key={i} label={`✗ ${c}`} color="#e74c3c" />)}
            </div>
            {r.behavioral_notes && (
              <div style={{fontSize:"0.75rem",color:"#555",fontStyle:"italic",borderTop:"1px solid rgba(255,255,255,0.05)",paddingTop:"0.625rem"}}>
                {r.behavioral_notes}
              </div>
            )}
            <div style={{fontSize:"0.7rem",color:"#444",marginTop:"0.625rem"}}>
              Simulated as <strong style={{color:"#666"}}>{r.user?.user_id?.slice(0,14) || "manual"}</strong> · {city} · {naijaTraits.join(", ")}
            </div>
          </div>
        ))}
      </main>
    </div>
  );
}

const SectionLabel = ({children}) => <div style={{fontFamily:"'Syne',sans-serif",fontSize:"0.63rem",fontWeight:600,letterSpacing:"0.15em",textTransform:"uppercase",color:"#555",marginBottom:"0.625rem"}}>{children}</div>;
const Field = ({label,children}) => <div style={{marginBottom:"0.875rem"}}><label style={{display:"block",fontSize:"0.75rem",color:"#888",marginBottom:4}}>{label}</label>{children}</div>;
const Pill = ({label,color}) => <span style={{fontSize:"0.72rem",padding:"3px 10px",borderRadius:100,background:color?`${color}15`:"#1a1a1a",border:`1px solid ${color?`${color}40`:"rgba(255,255,255,0.08)"}`,color:color||"#888"}}>{label}</span>;

const inp = {width:"100%",background:"#1a1a1a",border:"1px solid rgba(255,255,255,0.08)",borderRadius:8,color:"#f0ece4",fontFamily:"'DM Sans',sans-serif",fontSize:"0.875rem",padding:"0.6rem 0.85rem",outline:"none"};
const tagStyle = {fontSize:"0.72rem",padding:"3px 9px",borderRadius:100,border:"1px solid rgba(255,255,255,0.08)",cursor:"pointer",background:"transparent",color:"#888",fontFamily:"'DM Sans',sans-serif",transition:"all 0.15s"};
const tagActive = {background:"#F5A623",borderColor:"#F5A623",color:"#000",fontWeight:500};
const btnStyle = {width:"100%",padding:"0.85rem",background:"#F5A623",color:"#000",fontFamily:"'Syne',sans-serif",fontWeight:700,fontSize:"0.9rem",border:"none",borderRadius:10,marginTop:"0.5rem"};
const cardStyle = {background:"#141414",border:"1px solid rgba(255,255,255,0.08)",borderRadius:14,padding:"1.5rem",marginBottom:"1.25rem"};
