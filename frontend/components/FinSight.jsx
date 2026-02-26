"use client";
import { useState, useEffect } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area, CartesianGrid } from "recharts";
import { useSignals }   from "@/hooks/useSignals";
import { useWatchlist } from "@/hooks/useWatchlist";
import { useMarkets }   from "@/hooks/useMarkets";
import { useChartData } from "@/hooks/useChartData";

// ─── AFFILIATE BROKERS ────────────────────────────────────────────────────────
// TODO: Replace href values with your personal affiliate URLs after signing up
// Stake affiliate: partners.stake.com.au
// eToro affiliate: etoro.com/partners
// Swyftx affiliate: swyftx.com/affiliates
// CoinSpot referral: coinspot.com.au (referral in account settings)
// SelfWealth affiliate: selfwealth.com.au/affiliates
const BROKERS = [
  { name: "Stake",            tag: "ASX + US",   badge: "#58a6ff", href: "https://stake.com.au",        desc: "Stocks & ETFs" },
  { name: "SelfWealth",       tag: "ASX",        badge: "#4ade80", href: "https://selfwealth.com.au",   desc: "Flat-fee ASX trading" },
  { name: "eToro",            tag: "US + Crypto", badge: "#fbbf24", href: "https://etoro.com",          desc: "Social trading platform" },
  { name: "Swyftx",           tag: "Crypto",     badge: "#a78bfa", href: "https://swyftx.com",          desc: "Australian crypto exchange" },
  { name: "CoinSpot",         tag: "Crypto",     badge: "#a78bfa", href: "https://coinspot.com.au",     desc: "Buy 300+ coins in AUD" },
  { name: "Interactive Brokers", tag: "US + ASX", badge: "#f87171", href: "https://interactivebrokers.com.au", desc: "Pro-grade trading" },
];

// ─── SIGNAL CONFIG ────────────────────────────────────────────────────────────

const SIGNAL_CONFIG = {
  BUY:   { colour: "#4ade80", bg: "rgba(74,222,128,0.12)",  border: "rgba(74,222,128,0.3)",  label: "BUY ↑" },
  SELL:  { colour: "#16a34a", bg: "rgba(22,163,74,0.12)",   border: "rgba(22,163,74,0.3)",   label: "SELL ↑" },
  AVOID: { colour: "#f87171", bg: "rgba(248,113,113,0.12)", border: "rgba(248,113,113,0.3)", label: "AVOID ↓" },
  WATCH: { colour: "#fbbf24", bg: "rgba(251,191,36,0.12)",  border: "rgba(251,191,36,0.3)",  label: "WATCH ◈" },
};

// ─── HELPERS ──────────────────────────────────────────────────────────────────

function timeAgo(isoString) {
  if (!isoString) return "—";
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)  return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

// ─── COMPONENTS ───────────────────────────────────────────────────────────────

function LiveDot() {
  return (
    <span className="relative flex h-2 w-2">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
    </span>
  );
}

function SignalPill({ signal, size = "sm" }) {
  const cfg = SIGNAL_CONFIG[signal] || SIGNAL_CONFIG.WATCH;
  return (
    <span style={{
      background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.colour,
      padding: size === "sm" ? "2px 8px" : "4px 12px",
      borderRadius: 999, fontSize: size === "sm" ? 11 : 13, fontWeight: 700,
      fontFamily: "monospace", letterSpacing: "0.05em", whiteSpace: "nowrap"
    }}>
      {cfg.label}
    </span>
  );
}

function CredBar({ score }) {
  const pct = Math.round((score || 0) * 100);
  const col = pct >= 90 ? "#4ade80" : pct >= 75 ? "#fbbf24" : "#f87171";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 10, color: "#6b7280" }}>SOURCE</span>
      <div style={{ width: 40, height: 3, background: "#1f2937", borderRadius: 9 }}>
        <div style={{ width: `${pct}%`, height: "100%", background: col, borderRadius: 9, transition: "width 0.5s" }} />
      </div>
      <span style={{ fontSize: 10, color: col, fontWeight: 600 }}>{pct}%</span>
    </div>
  );
}

function ImpactMeter({ value }) {
  const col  = value >= 0 ? "#4ade80" : "#f87171";
  const sign = value >= 0 ? "+" : "";
  return (
    <div style={{ textAlign: "right" }}>
      <div style={{ fontSize: 22, fontWeight: 800, color: col, lineHeight: 1, fontFamily: "monospace" }}>
        {sign}{Math.round((value || 0) * 100)}
      </div>
      <div style={{ fontSize: 9, color: "#4b5563", textTransform: "uppercase", letterSpacing: "0.1em" }}>impact</div>
    </div>
  );
}

function SignalCard({ item, isNew }) {
  const [expanded, setExpanded] = useState(false);
  const [flash, setFlash]       = useState(isNew);
  const cfg = SIGNAL_CONFIG[item.signal] || SIGNAL_CONFIG.WATCH;

  useEffect(() => {
    if (isNew) { const t = setTimeout(() => setFlash(false), 2000); return () => clearTimeout(t); }
  }, [isNew]);

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      style={{
        background:   flash ? "rgba(74,222,128,0.05)" : "#0d1117",
        border:       `1px solid ${expanded ? cfg.border : "#1f2937"}`,
        borderLeft:   `3px solid ${cfg.colour}`,
        borderRadius: 10, padding: "14px 16px", cursor: "pointer",
        transition:   "all 0.3s", marginBottom: 8,
        transform:    flash ? "scale(1.005)" : "scale(1)",
        boxShadow:    flash ? `0 0 20px ${cfg.colour}20` : "none",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", marginBottom: 6 }}>
            <SignalPill signal={item.signal} />
            <span style={{ fontSize: 10, background: "#161b22", border: "1px solid #30363d", color: "#8b949e", padding: "2px 7px", borderRadius: 4, fontFamily: "monospace" }}>
              {item.market}
            </span>
            {/* Twitter badge */}
            {item.is_twitter && (
              <span style={{ fontSize: 10, background: "rgba(29,161,242,0.1)", border: "1px solid rgba(29,161,242,0.3)", color: "#1da1f2", padding: "2px 7px", borderRadius: 4, fontFamily: "monospace" }}>
                𝕏 @{item.twitter_handle}
              </span>
            )}
            {(item.tickers || []).slice(0, 2).map(t => (
              <span key={t} style={{ fontSize: 10, color: "#58a6ff", background: "rgba(88,166,255,0.1)", border: "1px solid rgba(88,166,255,0.2)", padding: "2px 6px", borderRadius: 4, fontFamily: "monospace" }}>{t}</span>
            ))}
            {(item.tickers || []).length > 2 && (
              <span style={{ fontSize: 10, color: "#6b7280" }}>+{item.tickers.length - 2} more</span>
            )}
            {/* Pump & dump risk badge — only show MEDIUM or HIGH */}
            {item.pump_dump_risk === "HIGH" && (
              <span style={{ fontSize: 10, background: "rgba(248,113,113,0.12)", border: "1px solid rgba(248,113,113,0.35)", color: "#f87171", padding: "2px 7px", borderRadius: 4, fontFamily: "monospace", fontWeight: 700 }}>
                ⚠ HYPE RISK
              </span>
            )}
            {item.pump_dump_risk === "MEDIUM" && (
              <span style={{ fontSize: 10, background: "rgba(251,191,36,0.1)", border: "1px solid rgba(251,191,36,0.3)", color: "#fbbf24", padding: "2px 7px", borderRadius: 4, fontFamily: "monospace", fontWeight: 700 }}>
                ⚡ UNVERIFIED
              </span>
            )}
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#e6edf3", lineHeight: 1.4, marginBottom: 5 }}>{item.title}</div>
          <div style={{ fontSize: 12, color: "#8b949e", lineHeight: 1.5 }}>{item.summary}</div>
          {/* Signal logic — plain-English "why" badge */}
          {item.signal_logic && (
            <div style={{
              marginTop: 7, display: "inline-block",
              fontSize: 10, fontWeight: 700, fontFamily: "monospace",
              background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.colour,
              padding: "3px 9px", borderRadius: 5, letterSpacing: "0.03em",
            }}>
              ▸ {item.signal_logic}
            </div>
          )}
        </div>
        <ImpactMeter value={item.impact} />
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 10 }}>
        <CredBar score={item.credibility} />
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 10, color: "#6b7280" }}>{item.source} · {timeAgo(item.published_at)}</span>
          <span style={{ fontSize: 10, color: "#4b5563", fontFamily: "monospace" }}>
            {Math.round((item.confidence || 0) * 100)}% conf
          </span>
          <span style={{ fontSize: 11, color: cfg.colour, transform: expanded ? "rotate(180deg)" : "none", transition: "transform 0.2s", display: "inline-block" }}>▾</span>
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #1f2937" }}>
          <div style={{ fontSize: 11, color: "#8b949e", lineHeight: 1.7, fontStyle: "italic" }}>
            {item.reasoning}
          </div>
          <div style={{ marginTop: 8, fontSize: 10, color: "#4b5563" }}>
            ⚠ FinSight does not guarantee or influence any financial decisions. Signals are derived from publicly available news and automated analysis only. Please do your own research.
          </div>
        </div>
      )}
    </div>
  );
}

// ─── MAIN APP ─────────────────────────────────────────────────────────────────

export default function FinSight() {
  const [filter,        setFilter]      = useState("ALL");
  const [activeTab,     setActiveTab]   = useState("signals");
  const [plan,          setPlan]        = useState("FREE");
  const [showUpgrade,   setShowUpgrade] = useState(false);
  const [tickerInput,   setTickerInput] = useState("");
  const [time,          setTime]        = useState(new Date());

  // Beta signup form state
  const [betaStep,      setBetaStep]    = useState("pick");   // "pick" | "form" | "verify" | "done"
  const [betaChoice,    setBetaChoice]  = useState("PRO");
  const [betaName,      setBetaName]    = useState("");
  const [betaEmail,     setBetaEmail]   = useState("");
  const [betaOtp,       setBetaOtp]     = useState("");
  const [betaSubmitting,setBetaSubmitting] = useState(false);
  const [betaError,     setBetaError]   = useState("");

  // ── Real data hooks ──────────────────────────────────────────────────────
  const { signals, loading: sigLoading, newId } = useSignals(plan);
  const { watchlist, addTicker, removeTicker }  = useWatchlist();
  const { allMarkets }                           = useMarkets();
  const { chartData }                            = useChartData();

  // Clock
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const counts  = signals.reduce((a, s) => { a[s.signal] = (a[s.signal] || 0) + 1; return a; }, {});
  const filtered = filter === "ALL" ? signals : signals.filter(s => s.signal === filter);
  const isLocked = (s) => plan === "FREE" && signals.indexOf(s) >= 3;

  const avgConf = signals.length
    ? Math.round(signals.reduce((a, s) => a + (s.confidence || 0), 0) / signals.length * 100)
    : 0;

  const FILTER_TABS = ["ALL", "BUY", "SELL", "AVOID", "WATCH"];

  const handleAddTicker = async () => {
    const t = tickerInput.trim().toUpperCase();
    if (!t) return;
    await addTicker(t, t);
    setTickerInput("");
  };

  const handleBetaSubmit = async () => {
    if (!betaName.trim() || !betaEmail.trim()) {
      setBetaError("Please enter your name and email.");
      return;
    }
    setBetaError("");
    setBetaSubmitting(true);
    try {
      const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${BASE}/api/beta-signup`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ name: betaName.trim(), email: betaEmail.trim(), plan: betaChoice }),
      });
      if (!res.ok) {
        const err = await res.json();
        setBetaError(err.detail || "Something went wrong. Please try again.");
        return;
      }
      setBetaOtp("");
      setBetaStep("verify");
    } catch {
      setBetaError("Something went wrong. Please try again.");
    } finally {
      setBetaSubmitting(false);
    }
  };

  const handleBetaVerify = async () => {
    if (!betaOtp.trim()) {
      setBetaError("Please enter the verification code.");
      return;
    }
    setBetaError("");
    setBetaSubmitting(true);
    try {
      const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${BASE}/api/beta-verify`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ email: betaEmail.trim(), code: betaOtp.trim() }),
      });
      if (!res.ok) {
        const err = await res.json();
        setBetaError(err.detail || "Invalid code. Please try again.");
        return;
      }
      const data = await res.json();
      setPlan(data.plan);
      setBetaStep("done");
    } catch {
      setBetaError("Something went wrong. Please try again.");
    } finally {
      setBetaSubmitting(false);
    }
  };

  const openUpgrade = () => {
    setBetaStep("pick");
    setBetaName("");
    setBetaEmail("");
    setBetaOtp("");
    setBetaError("");
    setShowUpgrade(true);
  };

  return (
    <div style={{ background: "#010409", minHeight: "100vh", fontFamily: "'IBM Plex Mono', 'Courier New', monospace", color: "#e6edf3" }}>

      {/* ── Header ── */}
      <div style={{ background: "#0d1117", borderBottom: "1px solid #1f2937", padding: "0 24px" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between", height: 56 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 18, fontWeight: 900, letterSpacing: "-0.02em", background: "linear-gradient(135deg, #4ade80, #22d3ee)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>FINSIGHT</span>
              <span style={{ fontSize: 10, color: "#4b5563", border: "1px solid #1f2937", padding: "1px 6px", borderRadius: 3 }}>BETA</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "#4ade80" }}>
              <LiveDot />
              <span>LIVE</span>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <span style={{ fontSize: 11, color: "#4b5563", fontFamily: "monospace" }}>
              {time.toLocaleTimeString("en-AU", { hour12: false })} AEST
            </span>
            <div style={{ display: "flex", gap: 2 }}>
              {["signals", "watchlist", "markets"].map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)} style={{
                  background: activeTab === tab ? "#1f2937" : "transparent",
                  border: "none", color: activeTab === tab ? "#e6edf3" : "#6b7280",
                  padding: "6px 12px", borderRadius: 6, cursor: "pointer",
                  fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", transition: "all 0.2s"
                }}>{tab}</button>
              ))}
            </div>
            <div
              onClick={() => plan === "FREE" && openUpgrade()}
              style={{
                padding: "5px 12px", borderRadius: 6, fontSize: 11, fontWeight: 700,
                cursor: plan === "FREE" ? "pointer" : "default",
                background: plan === "FREE" ? "rgba(251,191,36,0.1)" : "rgba(74,222,128,0.1)",
                border: `1px solid ${plan === "FREE" ? "rgba(251,191,36,0.3)" : "rgba(74,222,128,0.3)"}`,
                color: plan === "FREE" ? "#fbbf24" : "#4ade80",
              }}>
              {plan === "FREE" ? "⚡ FREE PLAN" : `✦ ${plan} — BETA`}
            </div>
          </div>
        </div>
      </div>

      {/* ── Upgrade modal ── */}
      {showUpgrade && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
          <div style={{ background: "#0d1117", border: "1px solid #1f2937", borderRadius: 16, padding: 32, maxWidth: 480, width: "100%", position: "relative" }}>
            <button onClick={() => setShowUpgrade(false)} style={{ position: "absolute", top: 16, right: 16, background: "none", border: "none", color: "#6b7280", cursor: "pointer", fontSize: 18 }}>✕</button>

            {/* ── STEP 1: Pick a plan ── */}
            {betaStep === "pick" && (
              <>
                <div style={{ textAlign: "center", marginBottom: 8 }}>
                  <div style={{ fontSize: 11, color: "#4ade80", fontWeight: 700, letterSpacing: "0.1em", marginBottom: 8, textTransform: "uppercase" }}>🎉 Beta Launch — Free Access</div>
                  <div style={{ fontSize: 22, fontWeight: 900, marginBottom: 6 }}>Unlock FinSight Pro</div>
                  <div style={{ fontSize: 13, color: "#8b949e", lineHeight: 1.5 }}>Enjoy full Pro or Elite access completely free while we&apos;re in beta. No card needed.</div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20, marginTop: 20 }}>
                  {[
                    { plan: "PRO",   label: "PRO",   features: ["50 stocks", "Hourly refresh", "Full AI reasoning", "US + ASX markets"] },
                    { plan: "ELITE", label: "ELITE", features: ["Unlimited stocks", "Real-time signals", "All markets", "M&A analysis"] },
                  ].map(p => (
                    <div key={p.plan}
                      onClick={() => { setBetaChoice(p.plan); setBetaStep("form"); }}
                      style={{
                        background: p.plan === "ELITE" ? "rgba(74,222,128,0.05)" : "#161b22",
                        border: betaChoice === p.plan ? "1px solid #4ade80" : p.plan === "ELITE" ? "1px solid rgba(74,222,128,0.3)" : "1px solid #30363d",
                        borderRadius: 10, padding: 16, cursor: "pointer", transition: "all 0.2s",
                      }}>
                      <div style={{ fontWeight: 800, fontSize: 13, marginBottom: 4 }}>{p.label}</div>
                      <div style={{ fontSize: 13, fontWeight: 900, color: "#4ade80", marginBottom: 10 }}>FREE <span style={{ fontSize: 10, color: "#6b7280", fontWeight: 400 }}>during beta</span></div>
                      {p.features.map(f => <div key={f} style={{ fontSize: 11, color: "#8b949e", marginBottom: 3 }}>✓ {f}</div>)}
                      <div style={{ marginTop: 10, fontSize: 11, color: "#4ade80", fontWeight: 700 }}>Select {p.label} →</div>
                    </div>
                  ))}
                </div>
                <div style={{ fontSize: 10, color: "#4b5563", textAlign: "center" }}>Pricing applies after beta. Cancel anytime. Not financial advice.</div>
              </>
            )}

            {/* ── STEP 2: Enter details ── */}
            {betaStep === "form" && (
              <>
                <div style={{ textAlign: "center", marginBottom: 20 }}>
                  <div style={{ fontSize: 11, color: "#4ade80", fontWeight: 700, letterSpacing: "0.1em", marginBottom: 8, textTransform: "uppercase" }}>Almost there — {betaChoice} Plan</div>
                  <div style={{ fontSize: 20, fontWeight: 900, marginBottom: 6 }}>Get Free Beta Access</div>
                  <div style={{ fontSize: 12, color: "#8b949e", lineHeight: 1.5 }}>Drop your details and we&apos;ll unlock {betaChoice} instantly. We&apos;ll also notify you before pricing kicks in.</div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
                  <input
                    value={betaName}
                    onChange={e => setBetaName(e.target.value)}
                    placeholder="Your name"
                    style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 8, padding: "10px 14px", color: "#e6edf3", fontSize: 13, fontFamily: "monospace", outline: "none", width: "100%", boxSizing: "border-box" }}
                  />
                  <input
                    value={betaEmail}
                    onChange={e => setBetaEmail(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleBetaSubmit()}
                    placeholder="Your email address"
                    type="email"
                    style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 8, padding: "10px 14px", color: "#e6edf3", fontSize: 13, fontFamily: "monospace", outline: "none", width: "100%", boxSizing: "border-box" }}
                  />
                  {betaError && <div style={{ fontSize: 11, color: "#f87171" }}>{betaError}</div>}
                </div>
                <button
                  onClick={handleBetaSubmit}
                  disabled={betaSubmitting}
                  style={{ width: "100%", background: "linear-gradient(135deg, rgba(74,222,128,0.2), rgba(34,211,238,0.2))", border: "1px solid rgba(74,222,128,0.4)", color: "#4ade80", padding: "12px 0", borderRadius: 8, fontSize: 13, fontWeight: 800, cursor: betaSubmitting ? "not-allowed" : "pointer", fontFamily: "monospace", letterSpacing: "0.05em" }}>
                  {betaSubmitting ? "Unlocking..." : `Unlock ${betaChoice} Free →`}
                </button>
                <button onClick={() => setBetaStep("pick")} style={{ width: "100%", marginTop: 8, background: "none", border: "none", color: "#4b5563", fontSize: 11, cursor: "pointer", padding: "6px 0" }}>← Back</button>
                <div style={{ fontSize: 10, color: "#374151", textAlign: "center", marginTop: 8 }}>No spam. No card. We&apos;ll email you before beta ends.</div>
              </>
            )}

            {/* ── STEP 3: Verify OTP ── */}
            {betaStep === "verify" && (
              <>
                <div style={{ textAlign: "center", marginBottom: 20 }}>
                  <div style={{ fontSize: 28, marginBottom: 8 }}>📧</div>
                  <div style={{ fontSize: 20, fontWeight: 900, marginBottom: 6 }}>Check your email</div>
                  <div style={{ fontSize: 12, color: "#8b949e", lineHeight: 1.6 }}>
                    We sent a 6-digit code to<br />
                    <span style={{ color: "#4ade80", fontWeight: 700 }}>{betaEmail}</span>
                  </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
                  <input
                    value={betaOtp}
                    onChange={e => setBetaOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    onKeyDown={e => e.key === "Enter" && handleBetaVerify()}
                    placeholder="Enter 6-digit code"
                    maxLength={6}
                    style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 8, padding: "12px 14px", color: "#4ade80", fontSize: 20, fontFamily: "monospace", outline: "none", width: "100%", boxSizing: "border-box", textAlign: "center", letterSpacing: "0.3em" }}
                  />
                  {betaError && <div style={{ fontSize: 11, color: "#f87171" }}>{betaError}</div>}
                </div>
                <button
                  onClick={handleBetaVerify}
                  disabled={betaSubmitting || betaOtp.length < 6}
                  style={{ width: "100%", background: "linear-gradient(135deg, rgba(74,222,128,0.2), rgba(34,211,238,0.2))", border: "1px solid rgba(74,222,128,0.4)", color: "#4ade80", padding: "12px 0", borderRadius: 8, fontSize: 13, fontWeight: 800, cursor: (betaSubmitting || betaOtp.length < 6) ? "not-allowed" : "pointer", fontFamily: "monospace", letterSpacing: "0.05em" }}>
                  {betaSubmitting ? "Verifying..." : `Verify & Unlock ${betaChoice} →`}
                </button>
                <button onClick={() => { setBetaStep("form"); setBetaError(""); }} style={{ width: "100%", marginTop: 8, background: "none", border: "none", color: "#4b5563", fontSize: 11, cursor: "pointer", padding: "6px 0" }}>← Resend code</button>
                <div style={{ fontSize: 10, color: "#374151", textAlign: "center", marginTop: 8 }}>Code expires in 10 minutes.</div>
              </>
            )}

            {/* ── STEP 4: Success ── */}
            {betaStep === "done" && (
              <div style={{ textAlign: "center", padding: "8px 0" }}>
                <div style={{ fontSize: 40, marginBottom: 12 }}>🎉</div>
                <div style={{ fontSize: 22, fontWeight: 900, marginBottom: 8, background: "linear-gradient(135deg, #4ade80, #22d3ee)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                  Welcome to FinSight {betaChoice}!
                </div>
                <div style={{ fontSize: 13, color: "#8b949e", lineHeight: 1.7, marginBottom: 20 }}>
                  You&apos;re in. Enjoy full <span style={{ color: "#4ade80", fontWeight: 700 }}>{betaChoice}</span> access — completely free during our beta launch.<br />
                  We&apos;ll reach out before any pricing changes. Thanks for being an early supporter!
                </div>
                <button
                  onClick={() => setShowUpgrade(false)}
                  style={{ background: "linear-gradient(135deg, rgba(74,222,128,0.15), rgba(34,211,238,0.15))", border: "1px solid rgba(74,222,128,0.3)", color: "#4ade80", padding: "10px 28px", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: "monospace" }}>
                  Start Exploring →
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "20px 24px", display: "grid", gridTemplateColumns: "1fr 300px", gap: 20 }}>

        {/* ── Main content ── */}
        <div>

          {/* SIGNALS TAB */}
          {activeTab === "signals" && (
            <>
              <div style={{ display: "flex", gap: 6, marginBottom: 14, alignItems: "center" }}>
                {FILTER_TABS.map(f => {
                  const cfg    = f !== "ALL" ? SIGNAL_CONFIG[f] : null;
                  const active = filter === f;
                  return (
                    <button key={f} onClick={() => setFilter(f)} style={{
                      border:     active ? `1px solid ${cfg?.colour || "#58a6ff"}` : "1px solid #1f2937",
                      background: active ? (cfg ? cfg.bg : "rgba(88,166,255,0.1)") : "transparent",
                      color:      active ? (cfg?.colour || "#58a6ff") : "#6b7280",
                      padding: "5px 14px", borderRadius: 6, cursor: "pointer", fontSize: 11,
                      fontFamily: "monospace", fontWeight: 600, letterSpacing: "0.05em", transition: "all 0.2s",
                    }}>
                      {f} {f !== "ALL" && counts[f] ? <span style={{ opacity: 0.7 }}>({counts[f]})</span> : ""}
                    </button>
                  );
                })}
                <div style={{ marginLeft: "auto", fontSize: 11, color: "#4b5563" }}>{filtered.length} signals</div>
              </div>

              {sigLoading && (
                <div style={{ textAlign: "center", padding: 40, color: "#4b5563", fontSize: 12 }}>
                  Fetching live signals...
                </div>
              )}

              {!sigLoading && filtered.length === 0 && (
                <div style={{ textAlign: "center", padding: 40, color: "#4b5563", fontSize: 12, border: "1px dashed #1f2937", borderRadius: 10 }}>
                  No signals yet — the AI is scanning the news. Check back in a few minutes.
                </div>
              )}

              {filtered.map((item) =>
                isLocked(item) ? (
                  <div key={item.id} onClick={() => openUpgrade()} style={{
                    background: "#0d1117", border: "1px solid #1f2937", borderRadius: 10,
                    padding: "14px 16px", marginBottom: 8, cursor: "pointer",
                    filter: "blur(3px)", position: "relative", userSelect: "none",
                  }}>
                    <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
                      <SignalPill signal={item.signal} />
                      <span style={{ fontSize: 11, color: "#4b5563" }}>{(item.tickers || [])[0]}</span>
                    </div>
                    <div style={{ fontSize: 13, color: "#e6edf3" }}>{item.title}</div>
                    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", filter: "blur(0)", zIndex: 2 }}>
                      <span style={{ background: "#fbbf24", color: "#000", padding: "6px 14px", borderRadius: 999, fontSize: 11, fontWeight: 800 }}>⚡ PRO ONLY — Upgrade</span>
                    </div>
                  </div>
                ) : (
                  <SignalCard key={item.id} item={item} isNew={item.id === newId} />
                )
              )}
            </>
          )}

          {/* WATCHLIST TAB */}
          {activeTab === "watchlist" && (
            <div>
              <div style={{ marginBottom: 14, display: "flex", gap: 8 }}>
                <input
                  value={tickerInput}
                  onChange={e => setTickerInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleAddTicker()}
                  placeholder="Add ticker e.g. BHP.AX or AAPL..."
                  style={{ flex: 1, background: "#0d1117", border: "1px solid #1f2937", borderRadius: 8, padding: "8px 14px", color: "#e6edf3", fontSize: 12, fontFamily: "monospace", outline: "none" }}
                />
                <button onClick={handleAddTicker} style={{ background: "rgba(74,222,128,0.1)", border: "1px solid rgba(74,222,128,0.3)", color: "#4ade80", padding: "8px 18px", borderRadius: 8, cursor: "pointer", fontSize: 12, fontFamily: "monospace" }}>
                  + ADD
                </button>
              </div>

              {watchlist.length === 0 && (
                <div style={{ textAlign: "center", padding: 30, color: "#4b5563", fontSize: 12, border: "1px dashed #1f2937", borderRadius: 10 }}>
                  No tickers yet — add one above (e.g. BHP.AX, TSLA, BTC)
                </div>
              )}

              {watchlist.map(w => (
                <div key={w.ticker} style={{ background: "#0d1117", border: "1px solid #1f2937", borderRadius: 10, padding: "14px 16px", marginBottom: 8, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                      <span style={{ fontWeight: 700, fontSize: 13, fontFamily: "monospace" }}>{w.ticker}</span>
                      <span style={{ fontSize: 11, color: "#6b7280" }}>{w.name}</span>
                    </div>
                    <button onClick={() => removeTicker(w.ticker)} style={{ fontSize: 10, color: "#4b5563", background: "none", border: "none", cursor: "pointer", padding: 0 }}>remove</button>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    {w.price != null ? (
                      <>
                        <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "monospace" }}>
                          {w.currency === "AUD" ? "A$" : "$"}{w.price.toLocaleString()}
                        </div>
                        <div style={{ fontSize: 12, color: (w.change_pct || 0) >= 0 ? "#4ade80" : "#f87171", fontFamily: "monospace" }}>
                          {(w.change_pct || 0) >= 0 ? "▲" : "▼"} {Math.abs(w.change_pct || 0).toFixed(2)}%
                        </div>
                      </>
                    ) : (
                      <div style={{ fontSize: 12, color: "#4b5563" }}>loading…</div>
                    )}
                  </div>
                </div>
              ))}

              {plan === "FREE" && (
                <div onClick={() => openUpgrade()} style={{ textAlign: "center", padding: 20, border: "1px dashed #1f2937", borderRadius: 10, color: "#fbbf24", cursor: "pointer", fontSize: 12 }}>
                  ⚡ Free plan limited to 5 stocks. Upgrade to Pro for 50+
                </div>
              )}
            </div>
          )}

          {/* MARKETS TAB */}
          {activeTab === "markets" && (
            <div>
              <div style={{ background: "#0d1117", border: "1px solid #1f2937", borderRadius: 10, padding: 20, marginBottom: 16 }}>
                <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.08em" }}>Signal Activity — Today</div>
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={chartData.length ? chartData : [{ time: "Now", buy: 0, sell: 0, avoid: 0, watch: 0 }]}>
                    <defs>
                      <linearGradient id="buyGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#4ade80" stopOpacity={0.3} />
                        <stop offset="100%" stopColor="#4ade80" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="avoidGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#f87171" stopOpacity={0.3} />
                        <stop offset="100%" stopColor="#f87171" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                    <XAxis dataKey="time" tick={{ fill: "#6b7280", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: "#0d1117", border: "1px solid #1f2937", borderRadius: 8, fontSize: 11 }} />
                    <Area type="monotone" dataKey="buy"   stroke="#4ade80" fill="url(#buyGrad)"  strokeWidth={2} />
                    <Area type="monotone" dataKey="avoid" stroke="#f87171" fill="url(#avoidGrad)" strokeWidth={2} />
                    <Area type="monotone" dataKey="sell"  stroke="#16a34a" fill="none" strokeWidth={1.5} strokeDasharray="4 2" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {allMarkets.map(m => (
                <div key={m.name} style={{ background: "#0d1117", border: "1px solid #1f2937", borderRadius: 8, padding: "12px 16px", marginBottom: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 12, color: "#8b949e", fontFamily: "monospace" }}>{m.name}</span>
                  <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                    <span style={{ fontSize: 14, fontWeight: 700, fontFamily: "monospace" }}>{m.value}</span>
                    <span style={{ fontSize: 12, color: m.up ? "#4ade80" : "#f87171", fontFamily: "monospace" }}>{m.change}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Right panel ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

          {/* Signal mix bar chart */}
          <div style={{ background: "#0d1117", border: "1px solid #1f2937", borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: 10, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12 }}>Signal Mix</div>
            <ResponsiveContainer width="100%" height={130}>
              <BarChart data={[
                { name: "BUY",   v: counts.BUY   || 0 },
                { name: "SELL",  v: counts.SELL  || 0 },
                { name: "AVOID", v: counts.AVOID || 0 },
                { name: "WATCH", v: counts.WATCH || 0 },
              ]} barSize={28}>
                <XAxis dataKey="name" tick={{ fill: "#6b7280", fontSize: 9, fontFamily: "monospace" }} axisLine={false} tickLine={false} />
                <YAxis hide />
                <Tooltip contentStyle={{ background: "#0d1117", border: "1px solid #1f2937", borderRadius: 8, fontSize: 11 }} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                <Bar dataKey="v" radius={[4, 4, 0, 0]}
                  fill="#4ade80"
                  label={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Stats */}
          <div style={{ background: "#0d1117", border: "1px solid #1f2937", borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: 10, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12 }}>Today&apos;s Stats</div>
            {[
              { label: "Total Signals",  value: signals.length,       colour: "#e6edf3" },
              { label: "Buy Signals",    value: counts.BUY   || 0,    colour: "#4ade80" },
              { label: "Avoid Signals",  value: counts.AVOID || 0,    colour: "#f87171" },
              { label: "Avg Confidence", value: `${avgConf}%`,        colour: "#58a6ff" },
              { label: "AI Engine",      value: "Groq LLaMA",         colour: "#e6edf3" },
            ].map(row => (
              <div key={row.label} style={{ display: "flex", justifyContent: "space-between", marginBottom: 10, alignItems: "center" }}>
                <span style={{ fontSize: 11, color: "#6b7280" }}>{row.label}</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: row.colour, fontFamily: "monospace" }}>{row.value}</span>
              </div>
            ))}
          </div>

          {/* Upgrade CTA */}
          {plan === "FREE" && (
            <div onClick={() => openUpgrade()} style={{
              background: "linear-gradient(135deg, rgba(74,222,128,0.08), rgba(34,211,238,0.08))",
              border: "1px solid rgba(74,222,128,0.2)", borderRadius: 12, padding: 16, cursor: "pointer", textAlign: "center",
            }}>
              <div style={{ fontSize: 16, marginBottom: 4 }}>⚡</div>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4, color: "#4ade80" }}>Unlock Pro</div>
              <div style={{ fontSize: 11, color: "#8b949e", marginBottom: 10, lineHeight: 1.5 }}>50 stocks · Hourly alerts · Full AI reasoning</div>
              <div style={{ background: "rgba(74,222,128,0.15)", border: "1px solid rgba(74,222,128,0.3)", color: "#4ade80", padding: "7px 0", borderRadius: 7, fontSize: 11, fontWeight: 700 }}>
                $19/month →
              </div>
            </div>
          )}

          {/* Disclaimer */}
          <div style={{ padding: "10px 12px", background: "#0d1117", border: "1px solid rgba(251,191,36,0.25)", borderRadius: 8 }}>
            <div style={{ fontSize: 10, color: "#92400e", lineHeight: 1.6 }}>
              <span style={{ color: "#fbbf24", fontWeight: 700 }}>⚠ IMPORTANT:</span> FinSight does not guarantee any financial outcome or seek to influence your investment decisions. All signals are derived from publicly available news and automated speculation — not professional financial advice. Always do your own research before acting.
            </div>
          </div>

          {/* Automation business CTA */}
          <div style={{
            background: "linear-gradient(135deg, rgba(167,139,250,0.08), rgba(88,166,255,0.08))",
            border: "1px solid rgba(167,139,250,0.25)", borderRadius: 12, padding: 16,
          }}>
            <div style={{ fontSize: 10, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8, fontWeight: 700 }}>
              ⚙ Want Personalised Stock Alerts?
            </div>
            <div style={{ fontSize: 11, color: "#8b949e", lineHeight: 1.6, marginBottom: 6 }}>
              We can build you a smart automation that monitors the exact stocks in your portfolio and delivers real-time updates directly to your email or phone — tailored to your investments, not generic market noise.
            </div>
            <div style={{ fontSize: 11, color: "#a78bfa", lineHeight: 1.5, marginBottom: 12, fontStyle: "italic" }}>
              Reach out and let&apos;s build it together.
            </div>
            <a
              href="mailto:hello@saramsaautomation.com.au?subject=Stock Automation Inquiry from FinSight"
              style={{
                display: "block", textAlign: "center", textDecoration: "none",
                background: "rgba(167,139,250,0.15)", border: "1px solid rgba(167,139,250,0.35)",
                color: "#a78bfa", padding: "8px 0", borderRadius: 7, fontSize: 11, fontWeight: 700,
              }}
            >
              hello@saramsaautomation.com.au →
            </a>
          </div>
        </div>
      </div>

      {/* ── Broker affiliate section ── */}
      <div style={{ borderTop: "1px solid #1f2937", padding: "20px 24px 8px" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
            <span style={{ fontSize: 10, color: "#4b5563", textTransform: "uppercase", letterSpacing: "0.1em" }}>
              Open a trading account
            </span>
            <div style={{ flex: 1, height: 1, background: "#1f2937" }} />
            <span style={{ fontSize: 9, color: "#374151" }}>FinSight may earn a referral fee</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 8 }}>
            {BROKERS.map(b => (
              <a key={b.name} href={b.href} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none" }}>
                <div style={{
                  background: "#0d1117", border: "1px solid #1f2937", borderRadius: 8,
                  padding: "10px 12px", transition: "border-color 0.2s", cursor: "pointer",
                  display: "flex", flexDirection: "column", gap: 4,
                }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = "#30363d"}
                  onMouseLeave={e => e.currentTarget.style.borderColor = "#1f2937"}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: "#e6edf3" }}>{b.name}</span>
                    <span style={{ fontSize: 9, background: `${b.badge}18`, border: `1px solid ${b.badge}40`, color: b.badge, padding: "1px 5px", borderRadius: 3, fontFamily: "monospace" }}>{b.tag}</span>
                  </div>
                  <span style={{ fontSize: 10, color: "#6b7280" }}>{b.desc}</span>
                  <span style={{ fontSize: 10, color: "#4ade80", marginTop: 2 }}>Open account →</span>
                </div>
              </a>
            ))}
          </div>
        </div>
      </div>

      {/* ── Full-width disclaimer footer ── */}
      <div style={{ borderTop: "1px solid #1f2937", padding: "16px 24px", marginTop: 8 }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", textAlign: "center" }}>
          <div style={{ fontSize: 10, color: "#374151", lineHeight: 1.7 }}>
            <span style={{ color: "#4b5563", fontWeight: 700 }}>⚠ DISCLAIMER:</span>{" "}
            FinSight is an informational automation tool only. This site does not guarantee any financial result, nor does it seek to influence your investment decisions. All signals are derived from publicly available news and automated analysis — not professional financial advice. Past signals are not indicative of future performance. FinSight is not an AFSL licensee. Always conduct your own research and seek advice from a licensed financial adviser before making any investment decision.
          </div>
          <div style={{ fontSize: 9, color: "#1f2937", marginTop: 8 }}>
            © {new Date().getFullYear()} FinSight · Powered by Groq AI · Built by Saramsa Automation
          </div>
        </div>
      </div>
    </div>
  );
}
