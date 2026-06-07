import { useState } from 'react'

const API_URL = 'https://046giqhktg.execute-api.ap-south-1.amazonaws.com/prod/enroll'

const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

const URGENCY_OPTIONS = [
  { value: 'CRITICAL', label: 'CRITICAL', color: 'text-red-400' },
  { value: 'HIGH',     label: 'HIGH',     color: 'text-orange-400' },
  { value: 'NORMAL',   label: 'NORMAL',   color: 'text-emerald-400' },
]

const inputClass =
  'w-full bg-[#0c0c20] border border-[#1e1e40] text-[#c0c0e0] rounded-lg px-4 py-2.5 text-sm outline-none focus:border-red-500/50 transition-colors placeholder:text-[#3a3a60]'

const labelClass = 'text-[10px] font-mono tracking-widest text-[#3a3a7a] mb-1.5 block'

export default function PatientPortal() {
  const [form, setForm] = useState({
    name: '',
    blood_group: '',
    phone: '',
    city: '',
    urgency: '',
    latitude: '',
    longitude: '',
    age: '',
  })
  const [locating, setLocating] = useState(false)
  const [locationError, setLocationError] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const update = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }))

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setLocationError('Geolocation is not supported by your browser')
      return
    }
    setLocating(true)
    setLocationError('')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setForm(f => ({
          ...f,
          latitude: String(pos.coords.latitude),
          longitude: String(pos.coords.longitude),
        }))
        setLocating(false)
      },
      (err) => {
        setLocationError(err.message || 'Unable to retrieve your location')
        setLocating(false)
      }
    )
  }

  const isValid =
    form.name.trim() &&
    form.blood_group &&
    form.phone.trim() &&
    form.urgency &&
    form.latitude !== '' &&
    form.longitude !== ''

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!isValid) return
    setLoading(true)
    setError('')

    try {
      const payload = {
        name: form.name.trim(),
        blood_group: form.blood_group,
        latitude: parseFloat(form.latitude),
        longitude: parseFloat(form.longitude),
        phone: form.phone.trim(),
        urgency: form.urgency,
      }
      if (form.city.trim()) payload.city = form.city.trim()
      if (form.age !== '') payload.age = parseInt(form.age, 10)

      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Enrollment failed. Please try again.')

      setResult(data)
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <div className="mb-8">
        <div className="text-[10px] font-mono tracking-widest text-[#303060] mb-1">PATIENT / SELF-ENROLLMENT</div>
        <h1 className="text-2xl font-bold text-[#e0e0f4] tracking-wide">Request Blood</h1>
        <p className="text-[13px] text-[#4a4a80] mt-1">Tell us who you are and where you are — we'll match you with nearby donors</p>
      </div>

      {/* Success state */}
      {result && (
        <div className="bg-[#0b0b1e] border-2 border-emerald-500/40 rounded-2xl p-8 text-center">
          <div className="text-4xl mb-3">✅</div>
          <div className="text-[10px] font-mono tracking-widest text-emerald-400 mb-2">ENROLLMENT CONFIRMED</div>
          <h2 className="text-xl font-bold text-[#e0e0f4] mb-4">{result.message}</h2>

          <div className="grid grid-cols-2 gap-3 max-w-sm mx-auto">
            <div className="bg-[#0d0d25] border border-[#1c1c3c] rounded-lg p-3">
              <div className="text-[9px] font-mono tracking-widest text-[#3a3a7a] mb-1">PATIENT ID</div>
              <div className="text-[12px] font-mono text-[#c0c0e0] break-all">{result.patient_id}</div>
            </div>
            <div className="bg-[#0d0d25] border border-[#1c1c3c] rounded-lg p-3">
              <div className="text-[9px] font-mono tracking-widest text-[#3a3a7a] mb-1">URGENCY</div>
              <div className={`text-[13px] font-bold font-mono ${
                result.urgency === 'CRITICAL' ? 'text-red-400' :
                result.urgency === 'HIGH' ? 'text-orange-400' : 'text-emerald-400'
              }`}>
                {result.urgency}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loading state */}
      {!result && loading && (
        <div className="bg-[#0b0b1e] border border-[#1a1a38] rounded-2xl p-10 flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-[#2a2a55] border-t-red-500 rounded-full animate-spin" />
          <div className="text-[11px] font-mono tracking-widest text-[#5050a0]">SUBMITTING ENROLLMENT...</div>
        </div>
      )}

      {/* Form state */}
      {!result && !loading && (
        <form onSubmit={handleSubmit} className="bg-[#0b0b1e] border border-[#1a1a38] rounded-2xl p-6 space-y-4">
          <div>
            <label className={labelClass}>FULL NAME</label>
            <input
              type="text"
              value={form.name}
              onChange={update('name')}
              placeholder="Enter your full name"
              className={inputClass}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>BLOOD GROUP</label>
              <select value={form.blood_group} onChange={update('blood_group')} className={inputClass}>
                <option value="">— select —</option>
                {BLOOD_GROUPS.map(bg => <option key={bg} value={bg}>{bg}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass}>URGENCY</label>
              <select value={form.urgency} onChange={update('urgency')} className={inputClass}>
                <option value="">— select —</option>
                {URGENCY_OPTIONS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div>
          </div>

          {form.urgency && (
            <div className="flex items-center gap-2 px-3 py-2 bg-[#0d0d25] border border-[#1c1c3c] rounded-lg">
              <span className="text-[10px] font-mono tracking-widest text-[#4a4a80]">SELECTED URGENCY</span>
              <span className={`text-[12px] font-bold font-mono ${URGENCY_OPTIONS.find(u => u.value === form.urgency)?.color}`}>
                {form.urgency}
              </span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>PHONE NUMBER</label>
              <input
                type="tel"
                value={form.phone}
                onChange={update('phone')}
                placeholder="+91 98765 43210"
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>CITY (OPTIONAL)</label>
              <input
                type="text"
                value={form.city}
                onChange={update('city')}
                placeholder="e.g. Hyderabad"
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label className={labelClass}>AGE (OPTIONAL)</label>
            <input
              type="number"
              min="0"
              value={form.age}
              onChange={update('age')}
              placeholder="e.g. 28"
              className={inputClass}
            />
          </div>

          <div className="border-t border-[#12123a] pt-4">
            <label className={labelClass}>LOCATION</label>
            <button
              type="button"
              onClick={useMyLocation}
              disabled={locating}
              className="w-full mb-3 py-2.5 rounded-lg font-bold text-[12px] tracking-widest font-mono bg-[#1a1a30] hover:bg-[#22223e] text-[#9090c0] border border-[#2a2a55] transition-all duration-200 disabled:opacity-50"
            >
              {locating ? 'LOCATING...' : '📍 USE MY LOCATION'}
            </button>

            {locationError && (
              <div className="mb-3 px-4 py-2 bg-red-900/20 border border-red-500/30 rounded-lg text-red-400 text-[12px] font-mono">
                {locationError}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>LATITUDE</label>
                <input
                  type="text"
                  value={form.latitude}
                  onChange={update('latitude')}
                  placeholder="e.g. 17.4239"
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>LONGITUDE</label>
                <input
                  type="text"
                  value={form.longitude}
                  onChange={update('longitude')}
                  placeholder="e.g. 78.4738"
                  className={inputClass}
                />
              </div>
            </div>
          </div>

          {error && (
            <div className="px-4 py-2 bg-red-900/20 border border-red-500/30 rounded-lg text-red-400 text-[13px] font-mono">
              ERROR: {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!isValid}
            className={`w-full py-3 rounded-lg font-bold text-sm tracking-widest font-mono transition-all duration-200
              ${isValid
                ? 'bg-red-600 hover:bg-red-500 text-white shadow-[0_0_20px_rgba(229,62,62,0.25)] hover:shadow-[0_0_30px_rgba(229,62,62,0.35)]'
                : 'bg-[#1a1a30] text-[#3a3a60] cursor-not-allowed'
              }`}
          >
            SUBMIT REQUEST →
          </button>
        </form>
      )}
    </main>
  )
}
