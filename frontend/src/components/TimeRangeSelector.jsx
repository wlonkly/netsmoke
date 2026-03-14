const RANGES = [
  { value: '3h', label: '3h' },
  { value: '12h', label: '12h' },
  { value: '24h', label: '24h' },
  { value: '1w', label: '1w' },
]

export default function TimeRangeSelector({ value, onChange }) {
  return (
    <div className="time-range-selector">
      {RANGES.map((r) => (
        <button
          key={r.value}
          className={`range-btn${value === r.value ? ' active' : ''}`}
          onClick={() => onChange(r.value)}
        >
          {r.label}
        </button>
      ))}
    </div>
  )
}
