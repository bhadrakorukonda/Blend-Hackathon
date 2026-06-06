export default function ScoreRing({ score, size = 56 }) {
  const r     = size * 0.38
  const cx    = size / 2
  const cy    = size / 2
  const circ  = 2 * Math.PI * r
  const dash  = (score / 100) * circ
  const color = score >= 70 ? '#10b981' : score >= 45 ? '#d97706' : '#e53e3e'
  const sw    = size * 0.075

  return (
    <svg width={size} height={size} style={{ flexShrink: 0 }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1a1a38" strokeWidth={sw} />
      <circle
        cx={cx} cy={cy} r={r}
        fill="none"
        stroke={color}
        strokeWidth={sw}
        strokeDasharray={`${dash.toFixed(1)} ${(circ - dash).toFixed(1)}`}
        strokeDashoffset={(circ / 4).toFixed(1)}
        strokeLinecap="round"
      />
      <text
        x={cx} y={cy + size * 0.09}
        textAnchor="middle"
        fontSize={size * 0.2}
        fontWeight="700"
        fill={color}
        fontFamily="ui-monospace, monospace"
      >
        {Math.round(score)}
      </text>
    </svg>
  )
}
