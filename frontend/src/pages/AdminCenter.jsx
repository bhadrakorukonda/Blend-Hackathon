import { useState, useEffect, useCallback } from 'react'
import { getAdminStats } from '../api'
import BloodBadge from '../components/BloodBadge'
import StatusBadge from '../components/StatusBadge'

const BG_COLOR = {
  'O Positive': '#e53e3e', 'O Negative': '#e53e3e',
  'A Positive': '#d97706', 'A Negative': '#d97706',
  'B Positive': '#3b82f6', 'B Negative': '#3b82f6',
  'AB Positive':'#8b5cf6', 'AB Negative':'#8b5cf6',
}

function timeAgo(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  if (isNaN(d)) return '—'
  const s = Math.floor((Date.now() - d) / 1000)
  if (s < 60)    return `${s}s ago`
  if (s < 3600)  return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function MiniRing({ label, count, total, color }) {
  const r    = 30, cx = 36, cy = 36
  const circ = 2 * Math.PI * r
  const pct  = total > 0 ? Math.min(count / total, 1) : 0
  const dash = pct * circ

  return (
    <div className="flex flex-col items-center gap-1.5">
      <svg width={72} height={72}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1a1a35" strokeWidth={5} />
        <circle
          cx={cx} cy={cy} r={r}
          fill="none" stroke={color} strokeWidth={5}
          strokeDasharray={`${dash.toFixed(1)} ${(circ - dash).toFixed(1)}`}
          strokeDashoffset={(circ / 4).toFixed(1)}
          strokeLinecap="round"
        />
        <text x={cx} y={cy + 5} textAnchor="middle" fontSize={14} fontWeight="700" fill={color} fontFamily="monospace">
          {count}
        </text>
      </svg>
      <span className="text-[10px] font-mono tracking-widest" style={{ color }}>{label}</span>
    </div>
  )
}

function RankPips({ rank, total = 5 }) {
  return (
    <div className="flex items-center gap-1">
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          className={`w-2 h-2 rounded-full ${i < rank ? 'bg-red-500' : 'bg-[#1e1e40]'}`}
        />
      ))}
      <span className="text-[10px] font-mono text-[#4a4a80] ml-1">{rank}/{total}</span>
    </div>
  )
}

export default function AdminCenter() {
  const [data, setData]             = useState(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)
  const [lastRefresh, setLastRefresh] = useState(null)

  const load = useCallback(async () => {
    try {
      const d = await getAdminStats()
      setData(d)
      setLastRefresh(new Date())
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 30000)
    return () => clearInterval(id)
  }, [load])

  const sc  = data?.status_counts || {}
  const ic  = data?.intent_counts || {}
  const bgd = data?.blood_group_demand || {}
  const reqs = data?.requests || []
  const responseTotal = (ic.YES || 0) + (ic.NO || 0) + (ic.MAYBE || 0) || 1
  const bgEntries = Object.entries(bgd).sort((a, b) => b[1] - a[1])
  const bgMax     = bgEntries[0]?.[1] || 1

  return (
    <main className="max-w-6xl mx-auto px-4 py-8">

      {/* Page title */}
      <div className="flex items-end justify-between mb-8">
        <div>
          <div className="text-[10px] font-mono tracking-widest text-[#3030606] mb-1">SYSTEM / ADMIN</div>
          <h1 className="text-2xl font-bold text-[#e0e0f4] tracking-wide">Command Center</h1>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-[11px] font-mono text-[#3a3a6a]">
              {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <span className="flex items-center gap-1.5 text-[11px] font-mono text-emerald-500">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 glow-dot" />
            LIVE
          </span>
          <button
            onClick={load}
            className="text-[11px] font-mono px-3 py-1.5 border border-[#1c1c3a] text-[#5050a0] rounded hover:text-[#9090c0] hover:border-[#2c2c50] transition-all"
          >
            REFRESH
          </button>
        </div>
      </div>

      {loading && !data && (
        <div className="flex items-center justify-center h-64 text-[#3a3a7a] font-mono text-sm">
          <svg className="animate-spin w-5 h-5 mr-3 text-red-500" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.3"/>
            <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
          </svg>
          LOADING TELEMETRY…
        </div>
      )}

      {error && (
        <div className="mb-6 px-4 py-3 bg-red-900/20 border border-red-500/30 rounded-xl text-red-400 text-[13px] font-mono">
          ERROR: {error}
        </div>
      )}

      {data && (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            {[
              { label: 'TOTAL REQUESTS',  value: data.total,                   color: 'text-[#d0d0e8]' },
              { label: 'CONFIRMED',       value: sc.confirmed || 0,            color: 'text-emerald-400' },
              { label: 'SUCCESS RATE',    value: `${data.success_rate || 0}%`, color: (data.success_rate || 0) >= 50 ? 'text-emerald-400' : 'text-red-400' },
              { label: 'AVG ESCALATIONS', value: data.avg_escalations || 0,   color: 'text-amber-400' },
            ].map(k => (
              <div key={k.label} className="bg-[#0b0b1e] border border-[#1a1a38] rounded-xl p-4">
                <div className={`text-3xl font-bold font-mono ${k.color}`}>{k.value}</div>
                <div className="text-[9px] font-mono tracking-widest text-[#3a3a7a] mt-2">{k.label}</div>
              </div>
            ))}
          </div>

          {/* Mid row: responses + status */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">

            {/* Donor responses */}
            <div className="bg-[#0b0b1e] border border-[#1a1a38] rounded-xl p-5">
              <div className="text-[10px] font-mono tracking-widest text-[#3a3a7a] mb-4">DONOR RESPONSES</div>
              <div className="flex items-center gap-6">
                <MiniRing label="YES"   count={ic.YES   || 0} total={responseTotal} color="#10b981" />
                <MiniRing label="NO"    count={ic.NO    || 0} total={responseTotal} color="#e53e3e" />
                <MiniRing label="MAYBE" count={ic.MAYBE || 0} total={responseTotal} color="#d97706" />
                <div className="flex-1 text-right text-[11px] font-mono text-[#3a3a7a]">
                  {responseTotal === 1 ? 'No replies' : `${responseTotal} total`}
                </div>
              </div>
            </div>

            {/* Request status */}
            <div className="bg-[#0b0b1e] border border-[#1a1a38] rounded-xl p-5">
              <div className="text-[10px] font-mono tracking-widest text-[#3a3a7a] mb-4">REQUEST STATUS</div>
              <div className="flex flex-wrap gap-2">
                {['confirmed', 'pending', 'awaiting', 'escalate', 'exhausted']
                  .filter(s => sc[s] > 0)
                  .map(s => (
                    <div key={s} className="flex items-center gap-1.5">
                      <StatusBadge status={s} />
                      <span className="text-[12px] font-mono text-[#6060a0]">{sc[s]}</span>
                    </div>
                  ))}
                {Object.values(sc).every(v => v === 0) && (
                  <span className="text-[12px] font-mono text-[#3a3a7a]">No data</span>
                )}
              </div>
            </div>
          </div>

          {/* Blood group demand */}
          <div className="bg-[#0b0b1e] border border-[#1a1a38] rounded-xl p-5 mb-4">
            <div className="text-[10px] font-mono tracking-widest text-[#3a3a7a] mb-4">BLOOD GROUP DEMAND</div>
            {bgEntries.length > 0 ? (
              <div className="flex flex-col gap-3">
                {bgEntries.map(([group, count]) => (
                  <div key={group} className="flex items-center gap-3">
                    <div className="w-28 text-right">
                      <BloodBadge group={group} />
                    </div>
                    <div className="flex-1 h-2 bg-[#1a1a38] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${(count / bgMax * 100).toFixed(1)}%`,
                          background: BG_COLOR[group] || '#6060a0',
                        }}
                      />
                    </div>
                    <span className="text-[12px] font-mono text-[#5050a0] w-6 text-right">{count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <span className="text-[12px] font-mono text-[#3a3a7a]">No data</span>
            )}
          </div>

          {/* Live requests table */}
          <div className="bg-[#0b0b1e] border border-[#1a1a38] rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-[#12123a]">
              <div className="text-[10px] font-mono tracking-widest text-[#3a3a7a]">LIVE MATCH REQUESTS</div>
            </div>

            {reqs.length === 0 ? (
              <div className="px-5 py-12 text-center text-[#3a3a7a] font-mono text-sm">NO REQUESTS</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-[#12123a]">
                      {['REQUEST ID', 'BLOOD', 'STATUS', 'RANK', 'ESC', 'REPLY', 'CREATED', 'LAST OUTREACH'].map(h => (
                        <th key={h} className="px-4 py-3 text-[9px] font-mono tracking-widest text-[#3a3a7a]">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {reqs.map((req, i) => {
                      const dr     = req.donor_response
                      const intent = dr && typeof dr === 'object' ? dr.intent : null
                      const intentColor = { YES: 'text-emerald-400', NO: 'text-red-400', MAYBE: 'text-amber-400' }[intent] || 'text-[#4a4a80]'

                      return (
                        <tr
                          key={req.request_id}
                          className={`border-b border-[#0f0f28] transition-colors ${i % 2 === 0 ? 'bg-transparent' : 'bg-[#0d0d22]/40'} hover:bg-[#10102a]`}
                        >
                          <td className="px-4 py-3 font-mono text-[11px] text-[#4a4a80]">
                            {req.request_id.slice(0, 8).toUpperCase()}…
                          </td>
                          <td className="px-4 py-3">
                            <BloodBadge group={req.patient_blood_group} />
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadge status={req.status} />
                          </td>
                          <td className="px-4 py-3">
                            <RankPips rank={(req.current_donor_rank || 0) + 1} total={5} />
                          </td>
                          <td className="px-4 py-3 font-mono text-[12px]">
                            {(req.escalation_count || 0) > 0
                              ? <span className="text-red-500 font-bold">{req.escalation_count}×</span>
                              : <span className="text-[#3a3a7a]">—</span>}
                          </td>
                          <td className="px-4 py-3">
                            {intent
                              ? <span className={`font-mono text-[11px] font-bold ${intentColor}`}>{intent}</span>
                              : <span className="text-[#3a3a7a]">—</span>}
                          </td>
                          <td className="px-4 py-3 font-mono text-[11px] text-[#4a4a80]">{timeAgo(req.created_at)}</td>
                          <td className="px-4 py-3 font-mono text-[11px] text-[#4a4a80]">{timeAgo(req.last_outreach_at)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </main>
  )
}
