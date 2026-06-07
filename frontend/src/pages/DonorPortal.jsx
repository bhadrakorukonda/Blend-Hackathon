import { useState } from 'react'
import BloodBadge from '../components/BloodBadge'
import ScoreRing from '../components/ScoreRing'

const API_URL = 'https://046giqhktg.execute-api.ap-south-1.amazonaws.com/prod/admin'

const TIER_STYLES = {
  Bronze: 'bg-amber-900/30 text-amber-500 border-amber-600/40',
  Silver: 'bg-slate-500/20 text-slate-300 border-slate-400/40',
  Gold:   'bg-yellow-500/20 text-yellow-300 border-yellow-400/40',
}

const TIER_MESSAGES = {
  Bronze: "You're just getting started — every donation saves a life.",
  Silver: "You're a regular hero. Riya thanks you.",
  Gold:   "You're a Blood Warrior. Legend.",
}

const inputClass =
  'w-full bg-[#0c0c20] border border-[#1e1e40] text-[#c0c0e0] rounded-lg px-4 py-2.5 text-sm outline-none focus:border-red-500/50 transition-colors placeholder:text-[#3a3a60]'

function InfoTile({ label, value, highlight }) {
  return (
    <div className="bg-[#0d0d22] border border-[#1a1a38] rounded-lg p-3">
      <div className="text-[9px] font-mono tracking-widest text-[#3a3a7a] mb-1">{label}</div>
      <div className={`text-[13px] font-medium ${highlight ? 'text-emerald-400' : 'text-[#c0c0e0]'}`}>{value || '—'}</div>
    </div>
  )
}

export default function DonorPortal() {
  const [phone, setPhone] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notFound, setNotFound] = useState(false)
  const [profile, setProfile] = useState(null)

  const handleLookup = async (e) => {
    e.preventDefault()
    if (!phone.trim()) return
    setLoading(true)
    setError('')
    setNotFound(false)
    setProfile(null)

    try {
      const res = await fetch(`${API_URL}?phone=${encodeURIComponent(phone.trim())}`)
      if (res.status === 404) {
        setNotFound(true)
        return
      }
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Lookup failed. Please try again.')
      setProfile(data)
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setProfile(null)
    setNotFound(false)
    setError('')
    setPhone('')
  }

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <div className="mb-8">
        <div className="text-[10px] font-mono tracking-widest text-[#303060] mb-1">DONOR / SELF-SERVICE</div>
        <h1 className="text-2xl font-bold text-[#e0e0f4] tracking-wide">My Donor Profile</h1>
        <p className="text-[13px] text-[#4a4a80] mt-1">Look up your donation history and impact using your phone number</p>
      </div>

      {/* Lookup state */}
      {!profile && !loading && !notFound && (
        <form onSubmit={handleLookup} className="bg-[#0b0b1e] border border-[#1a1a38] rounded-2xl p-6 space-y-4">
          <div>
            <label className="text-[10px] font-mono tracking-widest text-[#3a3a7a] mb-1.5 block">PHONE NUMBER</label>
            <input
              type="tel"
              value={phone}
              onChange={e => setPhone(e.target.value)}
              placeholder="+91 98765 43210"
              className={inputClass}
            />
          </div>

          {error && (
            <div className="px-4 py-2 bg-red-900/20 border border-red-500/30 rounded-lg text-red-400 text-[13px] font-mono">
              ERROR: {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!phone.trim()}
            className={`w-full py-3 rounded-lg font-bold text-sm tracking-widest font-mono transition-all duration-200
              ${phone.trim()
                ? 'bg-red-600 hover:bg-red-500 text-white shadow-[0_0_20px_rgba(229,62,62,0.25)] hover:shadow-[0_0_30px_rgba(229,62,62,0.35)]'
                : 'bg-[#1a1a30] text-[#3a3a60] cursor-not-allowed'
              }`}
          >
            FIND MY PROFILE →
          </button>
        </form>
      )}

      {/* Loading state */}
      {loading && (
        <div className="bg-[#0b0b1e] border border-[#1a1a38] rounded-2xl p-10 flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-[#2a2a55] border-t-red-500 rounded-full animate-spin" />
          <div className="text-[11px] font-mono tracking-widest text-[#5050a0]">LOOKING UP YOUR PROFILE...</div>
        </div>
      )}

      {/* Not found state */}
      {notFound && !loading && (
        <div className="bg-[#0b0b1e] border-2 border-red-500/30 rounded-2xl p-8 text-center">
          <div className="text-4xl mb-3">🔍</div>
          <div className="text-[10px] font-mono tracking-widest text-red-400 mb-2">NO PROFILE FOUND</div>
          <p className="text-[14px] text-[#c0c0e0] mb-6">
            No donor profile found for this number. Are you registered? Contact Blood Warriors Foundation.
          </p>
          <button
            onClick={reset}
            className="px-6 py-2.5 rounded-lg font-bold text-[12px] tracking-widest font-mono bg-[#1a1a30] hover:bg-[#22223e] text-[#9090c0] border border-[#2a2a55] transition-all duration-200"
          >
            ← TRY ANOTHER NUMBER
          </button>
        </div>
      )}

      {/* Profile state */}
      {profile && !loading && (
        <div className="space-y-4">
          <div className="bg-[#0b0b1e] border border-[#1a1a38] rounded-2xl p-6">
            <div className="flex items-start justify-between gap-4 mb-5">
              <div>
                <div className="text-[10px] font-mono tracking-widest text-[#3a3a7a] mb-1">DONOR PROFILE</div>
                <h2 className="text-xl font-bold text-[#e0e0f4]">{profile.name || 'Donor'}</h2>
                <div className="flex items-center gap-2 mt-2 flex-wrap">
                  <BloodBadge group={profile.blood_group} />
                  {profile.city && (
                    <span className="text-[12px] font-mono text-[#5050a0]">📍 {profile.city}</span>
                  )}
                  <span className={`px-2.5 py-0.5 rounded-full border text-[10px] font-bold font-mono tracking-widest ${
                    profile.eligibility_status?.toLowerCase() === 'eligible'
                      ? 'bg-emerald-900/30 text-emerald-400 border-emerald-500/30'
                      : 'bg-red-900/30 text-red-400 border-red-500/30'
                  }`}>
                    {profile.eligibility_status?.toLowerCase() === 'eligible' ? 'ELIGIBLE' : 'NOT ELIGIBLE'}
                  </span>
                </div>
              </div>
              <div className="flex flex-col items-center gap-1 flex-shrink-0">
                <ScoreRing score={profile.reliability_score} size={72} />
                <span className="text-[9px] font-mono tracking-widest text-[#3a3a7a]">RELIABILITY</span>
              </div>
            </div>

            <div className="flex items-center gap-3 mb-5 px-4 py-3 bg-[#0d0d25] border border-[#1c1c3c] rounded-lg">
              <span className={`px-3 py-1 rounded-full border text-[11px] font-bold font-mono tracking-widest ${TIER_STYLES[profile.loyalty_tier] || TIER_STYLES.Bronze}`}>
                {profile.loyalty_tier?.toUpperCase() || 'BRONZE'} TIER
              </span>
              <span className="text-[12px] font-mono text-[#5050a0]">
                {profile.donations_till_date ?? 0} donation{profile.donations_till_date === 1 ? '' : 's'} so far
              </span>
            </div>

            <p className="text-[14px] text-[#d0d0e8] italic mb-5 px-1">
              "{TIER_MESSAGES[profile.loyalty_tier] || TIER_MESSAGES.Bronze}"
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              <InfoTile label="DONOR TYPE" value={profile.donor_type} />
              <InfoTile label="LAST DONATED" value={profile.last_donated_date} />
              <InfoTile label="NEXT ELIGIBLE" value={profile.next_eligible_date} highlight />
            </div>
          </div>

          <button
            onClick={reset}
            className="w-full py-2.5 rounded-lg font-bold text-[12px] tracking-widest font-mono bg-[#1a1a30] hover:bg-[#22223e] text-[#9090c0] border border-[#2a2a55] transition-all duration-200"
          >
            ← LOOK UP ANOTHER NUMBER
          </button>
        </div>
      )}
    </main>
  )
}
