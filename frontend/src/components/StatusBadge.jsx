const STYLES = {
  pending:   'bg-amber-500/10 text-amber-400 border-amber-500/30',
  awaiting:  'bg-blue-500/10  text-blue-400  border-blue-500/30',
  escalate:  'bg-red-500/10   text-red-400   border-red-500/30',
  confirmed: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  exhausted: 'bg-[#1a1a30]    text-[#4a4a80] border-[#2a2a50]',
}

export default function StatusBadge({ status, className = '' }) {
  const cls = STYLES[status] || 'bg-gray-800/50 text-gray-500 border-gray-600/30'
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded border text-[11px] font-bold font-mono tracking-wider ${cls} ${className}`}>
      {(status || 'unknown').toUpperCase()}
    </span>
  )
}
