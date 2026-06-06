const STYLES = {
  'O Negative':  'bg-red-900/30 text-red-400 border-red-500/30',
  'O Positive':  'bg-red-900/30 text-red-400 border-red-500/30',
  'A Negative':  'bg-amber-900/30 text-amber-400 border-amber-500/30',
  'A Positive':  'bg-amber-900/30 text-amber-400 border-amber-500/30',
  'B Negative':  'bg-blue-900/30 text-blue-400 border-blue-500/30',
  'B Positive':  'bg-blue-900/30 text-blue-400 border-blue-500/30',
  'AB Negative': 'bg-purple-900/30 text-purple-400 border-purple-500/30',
  'AB Positive': 'bg-purple-900/30 text-purple-400 border-purple-500/30',
}

export default function BloodBadge({ group, className = '' }) {
  const cls = STYLES[group] || 'bg-gray-800/50 text-gray-400 border-gray-600/30'
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded border text-[11px] font-bold font-mono tracking-wider ${cls} ${className}`}>
      {group || '?'}
    </span>
  )
}
