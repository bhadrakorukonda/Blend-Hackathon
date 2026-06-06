import { useState } from 'react'
import { findDonors } from '../api'
import { PATIENTS } from '../data/patients'
import ScoreRing from '../components/ScoreRing'
import BloodBadge from '../components/BloodBadge'

const RANK_COLORS = [
  { bg: 'bg-amber-500/20',  text: 'text-amber-400',  border: 'border-amber-500/40' },
  { bg: 'bg-slate-500/20',  text: 'text-slate-300',  border: 'border-slate-500/40' },
  { bg: 'bg-orange-900/30', text: 'text-orange-500', border: 'border-orange-600/40' },
  { bg: 'bg-[#1a1a35]',     text: 'text-[#7070c0]', border: 'border-[#2a2a55]' },
  { bg: 'bg-[#1a1a35]',     text: 'text-[#7070c0]', border: 'border-[#2a2a55]' },
]

function DonorCard({ donor, rank }) {
  const [open, setOpen] = useState(false)
  const rc = RANK_COLORS[rank] || RANK_COLORS[4]
  const type = donor.role || donor.donor_type || 'Donor'

  return (
    <div
      className={`border rounded-xl overflow-hidden transition-all duration-200
        ${open ? 'border-red-500/30 bg-[#0e0e22]' : 'border-[#1a1a38] bg-[#0b0b1e] hover:border-[#2a2a50]'}`}
    >
      {/* Card header */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
      >
        {/* Rank badge */}
        <span className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold font-mono border flex-shrink-0 ${rc.bg} ${rc.text} ${rc.border}`}>
          {rank + 1}
        </span>

        {/* Score ring */}
        <ScoreRing score={donor.score} size={52} />

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-medium text-[#d0d0e8] truncate">{type}</div>
          <div className="text-[11px] text-[#5050a0] mt-0.5 font-mono">
            {donor.distance_km} km &nbsp;·&nbsp; {donor.donations_till_date} donations
          </div>
        </div>

        <BloodBadge group={donor.blood_group} />

        {/* Chevron */}
        <span className={`text-[#3030606] text-xs ml-1 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>

      {/* Expanded details */}
      {open && (
        <div className="px-4 pb-4 border-t border-[#12123a]">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-3">
            {[
              { label: 'MATCH SCORE',    value: `${donor.score}/100` },
              { label: 'DISTANCE',       value: `${donor.distance_km} km` },
              { label: 'TOTAL DONATIONS',value: donor.donations_till_date || '0' },
              { label: 'CALL RATIO',     value: donor.calls_to_donations_ratio || '—' },
              { label: 'DONOR TYPE',     value: donor.donor_type || '—' },
              { label: 'ELIGIBILITY',    value: donor.eligibility_status || '—', highlight: donor.eligibility_status === 'eligible' },
              { label: 'LAST DONATION',  value: donor.last_donation_date || 'N/A' },
              { label: 'NEXT ELIGIBLE',  value: donor.next_eligible_date || 'N/A' },
              { label: 'GENDER',         value: donor.gender || '—' },
            ].map(({ label, value, highlight }) => (
              <div key={label} className="bg-[#0d0d22] border border-[#1a1a38] rounded-lg p-2.5">
                <div className="text-[9px] font-mono tracking-widest text-[#3a3a7a] mb-1">{label}</div>
                <div className={`text-[12px] font-medium ${highlight ? 'text-emerald-400' : 'text-[#c0c0e0]'}`}>
                  {value}
                </div>
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

  const selectedPatient = patientIdx !== '' ? PATIENTS[Number(patientIdx)] : null

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

  const donors = results?.top_donors || []
  const topDonor = donors[0]

  return (
    <main className="max-w-3xl mx-auto px-4 py-8">

      {/* Page title */}
      <div className="mb-8">
        <div className="text-[10px] font-mono tracking-widest text-[#3030606] mb-1">SYSTEM / COORDINATOR</div>
        <h1 className="text-2xl font-bold text-[#e0e0f4] tracking-wide">Match Initiator</h1>
        <p className="text-[13px] text-[#4a4a80] mt-1">Select a patient to scan the donor pool and initiate outreach</p>
      </div>

      {/* Patient selector panel */}
      {!results && (
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
            disabled={!selectedPatient || loading}
            className={`w-full py-3 rounded-lg font-bold text-sm tracking-widest font-mono transition-all duration-200
              ${selectedPatient && !loading
                ? 'bg-red-600 hover:bg-red-500 text-white shadow-[0_0_20px_rgba(229,62,62,0.25)] hover:shadow-[0_0_30px_rgba(229,62,62,0.35)]'
                : 'bg-[#1a1a30] text-[#3a3a60] cursor-not-allowed'
              }`}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.3"/>
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
                </svg>
                SCANNING DONOR POOL…
              </span>
            ) : 'INITIATE MATCH SEQUENCE →'}
          </button>
        </div>
      )}

      {/* Results panel */}
      {results && (
        <>
          {/* Result header */}
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-[10px] font-mono tracking-widest text-[#3a3a7a] mb-1">MATCH COMPLETE</div>
              <div className="flex items-center gap-3 flex-wrap">
                <BloodBadge group={results.patient_blood_group} />
                <span className="text-[12px] font-mono text-[#4a4a80]">
                  REQ #{(results.request_id || '').slice(0, 8).toUpperCase()}
                </span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-[11px] font-mono">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 glow-dot" />
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

          {/* Stats strip */}
          {topDonor && (
            <div className="grid grid-cols-3 gap-3 mb-5">
              {[
                { label: 'DONORS MATCHED', value: donors.length },
                { label: 'TOP SCORE',      value: topDonor.score?.toFixed(1) },
                { label: 'NEAREST',        value: `${topDonor.distance_km} km` },
              ].map(s => (
                <div key={s.label} className="bg-[#0b0b1e] border border-[#1a1a38] rounded-xl p-4 text-center">
                  <div className="text-2xl font-bold font-mono text-[#e0e0f4]">{s.value}</div>
                  <div className="text-[9px] font-mono tracking-widest text-[#3a3a7a] mt-1">{s.label}</div>
                </div>
              ))}
            </div>
          )}

          {/* Donor cards */}
          <div className="flex flex-col gap-2">
            {donors.map((donor, i) => (
              <DonorCard key={donor.user_id || i} donor={donor} rank={i} />
            ))}
          </div>
        </>
      )}
    </main>
  )
}
