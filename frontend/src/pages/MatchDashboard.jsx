import { useState, useEffect } from 'react'
import { findDonors } from '../api'
import { PATIENTS } from '../data/patients'
import ScoreRing from '../components/ScoreRing'
import BloodBadge from '../components/BloodBadge'

const SCAN_PHASES = [
  'BLOOD COMPATIBILITY CHECK',
  'ELIGIBILITY GATE VALIDATION',
  'DISTANCE SCORING',
  'RELIABILITY ANALYSIS',
  'AI RANKING IN PROGRESS',
]

const RANK_COLORS = [
  { bg: 'bg-slate-500/20',  text: 'text-slate-300',  border: 'border-slate-500/40' },
  { bg: 'bg-orange-900/30', text: 'text-orange-500', border: 'border-orange-600/40' },
  { bg: 'bg-[#1a1a35]',     text: 'text-[#7070c0]', border: 'border-[#2a2a55]' },
  { bg: 'bg-[#1a1a35]',     text: 'text-[#7070c0]', border: 'border-[#2a2a55]' },
]

function useCountUp(target, duration = 900) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    if (target === null || target === undefined) return
    const num = parseFloat(target) || 0
    if (num === 0) { setValue(0); return }
    const start = Date.now()
    let raf
    const tick = () => {
      const elapsed = Date.now() - start
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(eased * num)
      if (progress < 1) raf = requestAnimationFrame(tick)
      else setValue(num)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])
  return value
}

function StatCard({ label, rawValue, isInt = false, suffix = '' }) {
  const animated = useCountUp(parseFloat(rawValue) || 0)
  const display = isInt ? Math.round(animated) : animated.toFixed(1)
  return (
    <div className="bg-[#0b0b1e] border border-[#1a1a38] rounded-xl p-4 text-center">
      <div className="text-2xl font-bold font-mono text-[#e0e0f4]">{display}{suffix}</div>
      <div className="text-[9px] font-mono tracking-widest text-[#3a3a7a] mt-1">{label}</div>
    </div>
  )
}

function TopDonorCard({ donor }) {
  const type = donor.role || donor.donor_type || 'Donor'
  return (
    <div className="top-match-card border-2 border-red-500/60 rounded-2xl overflow-hidden relative bg-gradient-to-br from-[#120808] to-[#0e0e22]">
      <div className="absolute top-4 right-4 z-10">
        <span className="px-3 py-1 bg-red-600 text-white text-[10px] font-mono font-bold tracking-[0.18em] rounded-full shadow-[0_0_20px_rgba(229,62,62,0.6)]">
          TOP MATCH
        </span>
      </div>

      <div className="px-6 py-5 flex items-center gap-6">
        <div className="flex-shrink-0">
          <ScoreRing score={donor.score} size={88} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[9px] font-mono tracking-widest text-red-500/70 mb-1">#1 RANKED MATCH</div>
          <div className="text-xl font-bold text-[#e0e0f4] mb-2">{type}</div>
          <div className="flex items-center gap-3 flex-wrap">
            <BloodBadge group={donor.blood_group} />
            <span className="text-[12px] font-mono text-[#5050a0]">{donor.distance_km} km away</span>
            <span className="text-[12px] font-mono text-[#5050a0]">{donor.donations_till_date} donations</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 border-t border-red-500/20 divide-x divide-red-500/20">
        {[
          { label: 'MATCH SCORE', value: `${donor.score}/100` },
          { label: 'DONOR TYPE',  value: donor.donor_type || '—' },
          { label: 'ELIGIBILITY', value: donor.eligibility_status || '—', ok: donor.eligibility_status === 'eligible' },
        ].map(({ label, value, ok }) => (
          <div key={label} className="px-4 py-3 text-center">
            <div className="text-[9px] font-mono tracking-widest text-[#3a3a7a] mb-1">{label}</div>
            <div className={`text-[13px] font-bold font-mono ${ok ? 'text-emerald-400' : 'text-[#d0d0e8]'}`}>{value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function DonorCard({ donor, rank }) {
  const [open, setOpen] = useState(false)
  const rc = RANK_COLORS[rank - 1] || RANK_COLORS[RANK_COLORS.length - 1]
  const type = donor.role || donor.donor_type || 'Donor'

  return (
    <div
      className={`border rounded-xl overflow-hidden transition-all duration-200
        ${open ? 'border-red-500/30 bg-[#0e0e22]' : 'border-[#1a1a38] bg-[#0b0b1e] hover:border-[#2a2a50]'}`}
    >
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
      >
        <span className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold font-mono border flex-shrink-0 ${rc.bg} ${rc.text} ${rc.border}`}>
          {rank + 1}
        </span>
        <ScoreRing score={donor.score} size={52} />
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-medium text-[#d0d0e8] truncate">{type}</div>
          <div className="text-[11px] text-[#5050a0] mt-0.5 font-mono">
            {donor.distance_km} km &nbsp;·&nbsp; {donor.donations_till_date} donations
          </div>
        </div>
        <BloodBadge group={donor.blood_group} />
        <span className={`text-[#303060] text-xs ml-1 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>▼</span>
      </button>

      {open && (
        <div className="px-4 pb-4 border-t border-[#12123a]">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-3">
            {[
              { label: 'MATCH SCORE',     value: `${donor.score}/100` },
              { label: 'DISTANCE',        value: `${donor.distance_km} km` },
              { label: 'TOTAL DONATIONS', value: donor.donations_till_date || '0' },
              { label: 'CALL RATIO',      value: donor.calls_to_donations_ratio || '—' },
              { label: 'DONOR TYPE',      value: donor.donor_type || '—' },
              { label: 'ELIGIBILITY',     value: donor.eligibility_status || '—', highlight: donor.eligibility_status === 'eligible' },
              { label: 'LAST DONATION',   value: donor.last_donation_date || 'N/A' },
              { label: 'NEXT ELIGIBLE',   value: donor.next_eligible_date || 'N/A' },
              { label: 'GENDER',          value: donor.gender || '—' },
            ].map(({ label, value, highlight }) => (
              <div key={label} className="bg-[#0d0d22] border border-[#1a1a38] rounded-lg p-2.5">
                <div className="text-[9px] font-mono tracking-widest text-[#3a3a7a] mb-1">{label}</div>
                <div className={`text-[12px] font-medium ${highlight ? 'text-emerald-400' : 'text-[#c0c0e0]'}`}>{value}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function MatchDashboard() {
  const [patientIdx, setPatientIdx] = useState('')
  const [loading, setLoading]       = useState(false)
  const [results, setResults]       = useState(null)
  const [error, setError]           = useState(null)
  const [scanPhase, setScanPhase]   = useState(0)

  const selectedPatient = patientIdx !== '' ? PATIENTS[Number(patientIdx)] : null

  useEffect(() => {
    if (!loading) { setScanPhase(0); return }
    setScanPhase(0)
    const id = setInterval(() => setScanPhase(p => Math.min(p + 1, SCAN_PHASES.length - 1)), 450)
    return () => clearInterval(id)
  }, [loading])

  async function handleMatch() {
    if (!selectedPatient) return
    setLoading(true)
    setError(null)
    setResults(null)
    try {
      const data = await findDonors(selectedPatient.id)
      setResults(data)
    } catch (e) {
      setError(e.message || 'Match failed')
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setResults(null)
    setError(null)
    setPatientIdx('')
  }

  const donors    = results?.top_donors || []
  const topDonor  = donors[0]
  const restDonors = donors.slice(1)

  return (
    <main className="max-w-3xl mx-auto px-4 py-8">

      <div className="mb-8">
        <div className="text-[10px] font-mono tracking-widest text-[#303060] mb-1">SYSTEM / COORDINATOR</div>
        <h1 className="text-2xl font-bold text-[#e0e0f4] tracking-wide">Match Initiator</h1>
        <p className="text-[13px] text-[#4a4a80] mt-1">Select a patient to scan the donor pool and initiate outreach</p>
      </div>

      {/* Patient selector — hidden while loading or showing results */}
      {!results && !loading && (
        <div className="bg-[#0b0b1e] border border-[#1a1a38] rounded-2xl p-6 mb-6">
          <div className="text-[10px] font-mono tracking-widest text-[#3a3a7a] mb-3">PATIENT SELECTION</div>

          <select
            value={patientIdx}
            onChange={e => setPatientIdx(e.target.value)}
            className="w-full bg-[#0c0c20] border border-[#1e1e40] text-[#c0c0e0] rounded-lg px-4 py-2.5 text-sm mb-4 outline-none focus:border-red-500/50 transition-colors"
          >
            <option value="">— select patient —</option>
            {PATIENTS.map((p, i) => (
              <option key={p.id} value={i}>{p.label} · {p.bloodGroup}</option>
            ))}
          </select>

          {selectedPatient && (
            <div className="flex items-center gap-3 mb-4 px-3 py-2 bg-[#0d0d25] border border-[#1c1c3c] rounded-lg">
              <span className="text-[10px] font-mono tracking-widest text-[#4a4a80]">BLOOD REQUIRED</span>
              <BloodBadge group={selectedPatient.bloodGroup} />
            </div>
          )}

          {error && (
            <div className="mb-4 px-4 py-2 bg-red-900/20 border border-red-500/30 rounded-lg text-red-400 text-[13px] font-mono">
              ERROR: {error}
            </div>
          )}

          <button
            onClick={handleMatch}
            disabled={!selectedPatient}
            className={`w-full py-3 rounded-lg font-bold text-sm tracking-widest font-mono transition-all duration-200
              ${selectedPatient
                ? 'bg-red-600 hover:bg-red-500 text-white shadow-[0_0_20px_rgba(229,62,62,0.25)] hover:shadow-[0_0_30px_rgba(229,62,62,0.35)]'
                : 'bg-[#1a1a30] text-[#3a3a60] cursor-not-allowed'
              }`}
          >
            INITIATE MATCH SEQUENCE →
          </button>
        </div>
      )}

      {/* Scanning animation panel */}
      {loading && (
        <div className="bg-[#0b0b1e] border border-[#1a1a38] rounded-2xl p-6 mb-6 overflow-hidden">
          <div className="text-[10px] font-mono tracking-widest text-red-500 mb-1">SCANNING DONOR POOL</div>
          <div className="text-[15px] font-bold font-mono text-[#e0e0f4] mb-1">Scanning 7,033 donors...</div>
          <div className="text-[11px] text-[#4a4a80] font-mono mb-5">
            applying 4 compatibility filters · scoring 5 dimensions
          </div>

          <div className="relative h-[3px] bg-[#1a1a38] rounded-full mb-6 overflow-hidden">
            <div className="scan-beam" />
          </div>

          <div className="flex flex-col gap-2.5">
            {SCAN_PHASES.map((phase, i) => (
              <div
                key={phase}
                className={`flex items-center gap-3 transition-all duration-300 ${i <= scanPhase ? 'opacity-100' : 'opacity-20'}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 transition-colors duration-300
                  ${i <= scanPhase ? 'bg-red-500 glow-dot' : 'bg-[#2a2a50]'}`}
                />
                <span className={`text-[11px] font-mono transition-colors duration-300
                  ${i <= scanPhase ? 'text-[#a0a0cc]' : 'text-[#3a3a7a]'}`}
                >
                  {phase}
                  {i === scanPhase && <span className="ml-1 animate-pulse">_</span>}
                </span>
                {i < scanPhase && (
                  <span className="text-[9px] font-mono text-emerald-500 ml-auto tracking-widest">OK</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {results && (
        <>
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-[10px] font-mono tracking-widest text-[#3a3a7a] mb-1">MATCH COMPLETE</div>
              <div className="flex items-center gap-3 flex-wrap">
                <BloodBadge group={results.patient_blood_group} />
                <span className="text-[12px] font-mono text-[#4a4a80]">
                  REQ #{(results.request_id || '').slice(0, 8).toUpperCase()}
                </span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-[11px] font-mono">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 glow-dot" />
                  OUTREACH INITIATED
                </span>
              </div>
            </div>
            <button
              onClick={reset}
              className="text-[11px] font-mono px-3 py-1.5 border border-[#1c1c3a] text-[#5050a0] rounded hover:text-[#9090c0] hover:border-[#2c2c50] transition-all"
            >
              ← NEW SEARCH
            </button>
          </div>

          {/* Animated stats strip */}
          {topDonor && (
            <div className="grid grid-cols-3 gap-3 mb-4">
              <StatCard label="DONORS MATCHED" rawValue={donors.length} isInt />
              <StatCard label="TOP SCORE"      rawValue={topDonor.score} />
              <StatCard label="NEAREST"        rawValue={topDonor.distance_km} suffix=" km" />
            </div>
          )}

          {/* Top donor — dramatic full-width card */}
          {topDonor && (
            <div className="mb-3">
              <TopDonorCard donor={topDonor} />
            </div>
          )}

          {/* Remaining donors */}
          <div className="flex flex-col gap-2">
            {restDonors.map((donor, i) => (
              <DonorCard key={donor.user_id || i} donor={donor} rank={i + 1} />
            ))}
          </div>
        </>
      )}
    </main>
  )
}
