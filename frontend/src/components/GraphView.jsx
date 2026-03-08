import { useState, useEffect } from 'react'
import { graphUrl, fetchStats } from '../api.js'

const RANGES = [
  { value: '3h',  label: '3 hours' },
  { value: '2d',  label: '2 days' },
  { value: '1mo', label: '1 month' },
  { value: '1y',  label: '1 year' },
]

function GraphPanel({ target, range, label, imgKey }) {
  const url = graphUrl(target.path, range) + `&_k=${imgKey}`
  return (
    <div className="graph-panel">
      <div className="graph-panel-label">{label}</div>
      <div className="graph-container">
        <img
          src={url}
          alt={`${label} latency graph for ${target.name}`}
          className="graph-img"
        />
      </div>
    </div>
  )
}

export default function GraphView({ target }) {
  const [imgKey, setImgKey] = useState(0)
  const [stats, setStats] = useState(null)
  const [statsError, setStatsError] = useState(null)

  // Reload all graphs when target changes
  useEffect(() => {
    setImgKey((k) => k + 1)
  }, [target])

  // Auto-refresh every 60s
  useEffect(() => {
    const id = setInterval(() => setImgKey((k) => k + 1), 60_000)
    return () => clearInterval(id)
  }, [])

  // Fetch stats whenever target changes
  useEffect(() => {
    if (!target) return
    setStats(null)
    setStatsError(null)
    fetchStats(target.path)
      .then(setStats)
      .catch((e) => setStatsError(e.message))
  }, [target])

  if (!target) {
    return (
      <div className="graph-placeholder">
        <p>Select a target from the sidebar</p>
      </div>
    )
  }

  return (
    <div className="graph-view">
      <div className="graph-header">
        <div className="graph-title">
          <span className="graph-target-name">{target.name}</span>
          <span className="graph-target-host">{target.host}</span>
        </div>
        <div className="stats-bar">
          {stats ? (
            <>
              <span className="stat">
                <span className="stat-label">median</span>
                <span className="stat-value">
                  {stats.median_ms != null ? `${stats.median_ms.toFixed(1)} ms` : '—'}
                </span>
              </span>
              <span className="stat">
                <span className="stat-label">loss</span>
                <span className={`stat-value ${stats.loss_pct > 0 ? 'loss-nonzero' : ''}`}>
                  {stats.loss_pct != null ? `${stats.loss_pct}%` : '—'}
                </span>
              </span>
              <span className="stat">
                <span className="stat-label">samples (5m)</span>
                <span className="stat-value">{stats.sample_count}</span>
              </span>
            </>
          ) : statsError ? (
            <span className="stat-error">{statsError}</span>
          ) : null}
        </div>
      </div>

      <div className="graph-stack">
        {RANGES.map(({ value, label }) => (
          <GraphPanel
            key={value}
            target={target}
            range={value}
            label={label}
            imgKey={imgKey}
          />
        ))}
      </div>
    </div>
  )
}
