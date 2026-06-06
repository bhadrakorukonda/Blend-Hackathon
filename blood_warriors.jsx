import { useState, useEffect, useRef } from "react";

// ── Config ────────────────────────────────────────────────────────────────────
// Replace with your actual API Gateway invoke URL
const API_URL = "https://YOUR_API_GATEWAY_ID.execute-api.ap-south-1.amazonaws.com/prod/match";

// ── Blood group badge colors ──────────────────────────────────────────────────
const BG_COLORS = {
  "O Negative":  { bg: "#fff0f0", color: "#a32d2d", border: "#f09595" },
  "O Positive":  { bg: "#fff0f0", color: "#a32d2d", border: "#f09595" },
  "A Negative":  { bg: "#fff7e6", color: "#854f0b", border: "#ef9f27" },
  "A Positive":  { bg: "#fff7e6", color: "#854f0b", border: "#ef9f27" },
  "B Negative":  { bg: "#e6f1fb", color: "#185fa5", border: "#85b7eb" },
  "B Positive":  { bg: "#e6f1fb", color: "#185fa5", border: "#85b7eb" },
  "AB Negative": { bg: "#eeedfe", color: "#534ab7", border: "#afa9ec" },
  "AB Positive": { bg: "#eeedfe", color: "#534ab7", border: "#afa9ec" },
};

const bgStyle = (group) => BG_COLORS[group] || { bg: "#f1efe8", color: "#5f5e5a", border: "#b4b2a9" };

// ── Score ring ────────────────────────────────────────────────────────────────
function ScoreRing({ score }) {
  const pct = score / 100;
  const r = 20, cx = 26, cy = 26;
  const circ = 2 * Math.PI * r;
  const dash = pct * circ;
  const color = score >= 70 ? "#1d9e75" : score >= 45 ? "#ba7517" : "#a32d2d";
  return (
    <svg width={52} height={52} style={{ flexShrink: 0 }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#e5e5e5" strokeWidth={4} />
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth={4}
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeDashoffset={circ / 4}
        strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.6s ease" }}
      />
      <text x={cx} y={cy + 5} textAnchor="middle" fontSize={11} fontWeight={600} fill={color}>
        {Math.round(score)}
      </text>
    </svg>
  );
}

// ── Donor card ────────────────────────────────────────────────────────────────
function DonorCard({ donor, rank, visible }) {
  const c = bgStyle(donor.blood_group);
  const initials = (donor.name || "??").split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 14,
      padding: "14px 18px",
      background: "var(--color-background-primary)",
      border: "0.5px solid var(--color-border-tertiary)",
      borderRadius: 12,
      opacity: visible ? 1 : 0,
      transform: visible ? "translateY(0)" : "translateY(16px)",
      transition: `opacity 0.4s ease ${rank * 80}ms, transform 0.4s ease ${rank * 80}ms`,
    }}>
      {/* Rank */}
      <span style={{
        width: 22, height: 22, borderRadius: "50%",
        background: rank === 1 ? "#ef9f27" : "var(--color-background-secondary)",
        color: rank === 1 ? "#412402" : "var(--color-text-secondary)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 11, fontWeight: 600, flexShrink: 0,
      }}>{rank}</span>

      {/* Avatar */}
      <div style={{
        width: 40, height: 40, borderRadius: "50%",
        background: c.bg, border: `1px solid ${c.border}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 13, fontWeight: 600, color: c.color, flexShrink: 0,
      }}>{initials}</div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ margin: 0, fontWeight: 500, fontSize: 14, color: "var(--color-text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {donor.name || donor.user_id}
        </p>
        <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--color-text-secondary)" }}>
          {donor.donor_type || "Donor"} · {donor.distance_km} km away
        </p>
      </div>

      {/* Blood group badge */}
      <span style={{
        padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600,
        background: c.bg, color: c.color, border: `0.5px solid ${c.border}`,
        whiteSpace: "nowrap", flexShrink: 0,
      }}>{donor.blood_group}</span>

      {/* Score ring */}
      <ScoreRing score={donor.score} />
    </div>
  );
}

// ── Main app ──────────────────────────────────────────────────────────────────
export default function App() {
  const [patientId, setPatientId] = useState("");
  const [loading, setLoading]     = useState(false);
  const [result, setResult]       = useState(null);
  const [error, setError]         = useState("");
  const [visible, setVisible]     = useState(false);
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const handleMatch = async () => {
    if (!patientId.trim()) { setError("Please enter a patient ID."); return; }
    setLoading(true); setError(""); setResult(null); setVisible(false);

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_id: patientId.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setResult(data);
      setTimeout(() => setVisible(true), 50);
    } catch (e) {
      setError(e.message || "Something went wrong. Check your API URL.");
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => { if (e.key === "Enter") handleMatch(); };
  const reset = () => { setResult(null); setError(""); setPatientId(""); setVisible(false); setTimeout(() => inputRef.current?.focus(), 50); };

  return (
    <div style={{ maxWidth: 600, margin: "0 auto", padding: "2rem 1rem", fontFamily: "var(--font-sans)" }}>

      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: "2rem" }}>
        <div style={{
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          width: 56, height: 56, borderRadius: 16,
          background: "#fff0f0", border: "0.5px solid #f09595",
          fontSize: 26, marginBottom: 14,
        }}>🩸</div>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 500, color: "var(--color-text-primary)" }}>Blood Warriors</h1>
        <p style={{ margin: "6px 0 0", fontSize: 14, color: "var(--color-text-secondary)" }}>
          Find the top matched blood donors for any patient
        </p>
      </div>

      {/* Search card */}
      {!result && (
        <div style={{
          background: "var(--color-background-primary)",
          border: "0.5px solid var(--color-border-tertiary)",
          borderRadius: 16, padding: "1.5rem",
        }}>
          <label style={{ fontSize: 13, fontWeight: 500, color: "var(--color-text-secondary)", display: "block", marginBottom: 8 }}>
            Patient ID
          </label>
          <input
            ref={inputRef}
            value={patientId}
            onChange={e => { setPatientId(e.target.value); setError(""); }}
            onKeyDown={handleKey}
            placeholder="e.g. 01b2c2d3..."
            style={{ width: "100%", boxSizing: "border-box", marginBottom: 12 }}
          />
          {error && (
            <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--color-text-danger)" }}>
              {error}
            </p>
          )}
          <button
            onClick={handleMatch}
            disabled={loading}
            style={{ width: "100%", padding: "10px 0", fontSize: 14, fontWeight: 500,
              background: loading ? "var(--color-background-secondary)" : "#a32d2d",
              color: loading ? "var(--color-text-secondary)" : "#fff",
              border: "none", borderRadius: 8, cursor: loading ? "not-allowed" : "pointer",
              transition: "background 0.2s",
            }}
          >
            {loading ? "Finding donors…" : "Find top donors →"}
          </button>
        </div>
      )}

      {/* Results */}
      {result && (
        <div>
          {/* Summary row */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            marginBottom: "1rem",
          }}>
            <div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-secondary)" }}>Patient · {result.patient_id?.slice(0, 12)}…</p>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                <span style={{
                  padding: "3px 12px", borderRadius: 20, fontSize: 12, fontWeight: 600,
                  ...bgStyle(result.patient_blood_group)
                }}>{result.patient_blood_group}</span>
                {result.outreach_triggered && (
                  <span style={{
                    padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 500,
                    background: "var(--color-background-success)", color: "var(--color-text-success)",
                    border: "0.5px solid var(--color-border-success)",
                  }}>SMS sent ✓</span>
                )}
              </div>
            </div>
            <button onClick={reset} style={{ fontSize: 13, padding: "6px 14px" }}>
              ← New search
            </button>
          </div>

          {/* Stat chips */}
          <div style={{ display: "flex", gap: 10, marginBottom: "1.25rem" }}>
            {[
              { label: "Donors found", val: result.top_donors?.length ?? 0 },
              { label: "Top score", val: result.top_donors?.[0]?.score?.toFixed(1) ?? "—" },
              { label: "Nearest", val: result.top_donors?.[0] ? `${result.top_donors[0].distance_km} km` : "—" },
            ].map(s => (
              <div key={s.label} style={{
                flex: 1, background: "var(--color-background-secondary)",
                borderRadius: 10, padding: "10px 12px", textAlign: "center",
              }}>
                <p style={{ margin: 0, fontSize: 18, fontWeight: 500, color: "var(--color-text-primary)" }}>{s.val}</p>
                <p style={{ margin: "2px 0 0", fontSize: 11, color: "var(--color-text-secondary)" }}>{s.label}</p>
              </div>
            ))}
          </div>

          {/* Donor list */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {(result.top_donors || []).map((donor, i) => (
              <DonorCard key={donor.user_id} donor={donor} rank={i + 1} visible={visible} />
            ))}
          </div>

          {/* Request ID footer */}
          <p style={{ marginTop: "1.25rem", fontSize: 11, color: "var(--color-text-tertiary)", textAlign: "center" }}>
            Request ID: {result.request_id}
          </p>
        </div>
      )}
    </div>
  );
}