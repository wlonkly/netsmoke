import { useState, useEffect } from 'react'
import { graphUrl, fetchStats } from '../api.js'

const RANGE_SECONDS = {
  '3h':  3 * 3600,
  '2d':  2 * 24 * 3600,
  '1mo': 30 * 24 * 3600,
  '1y':  365 * 24 * 3600,
}

const RANGES = [
  { value: '3h',  label: '3 hours' },
  { value: '2d',  label: '2 days' },
  { value: '1mo', label: '1 month' },
  { value: '1y',  label: '1 year' },
]

function GraphPanel({ target, range, label, imgKey, startTs, endTs, onZoom }) {
  const url = graphUrl(target.path, range) + `&_k=${imgKey}`
  const [drag, setDrag] = useState(null)

  function handleMouseDown(e) {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    setDrag({ x0: x, x1: x, containerWidth: rect.width })
  }

  function handleMouseMove(e) {
    if (!drag) return
    const rect = e.currentTarget.getBoundingClientRect()
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width))
    setDrag((d) => ({ ...d, x1: x }))
  }

  function handleMouseUp(e) {
    if (!drag) return
    const { x0, x1, containerWidth } = drag
    setDrag(null)
    if (Math.abs(x1 - x0) < 5) return
    const left = Math.min(x0, x1)
    const right = Math.max(x0, x1)
    const selStart = Math.floor(startTs + (left / containerWidth) * (endTs - startTs))
    const selEnd = Math.floor(startTs + (right / containerWidth) * (endTs - startTs))
    if (onZoom) onZoom(selStart, selEnd)
  }

  const selectionStyle = drag
    ? { left: Math.min(drag.x0, drag.x1), width: Math.abs(drag.x1 - drag.x0) }
    : null

  return (
    <div className="graph-panel">
      <div className="graph-panel-label">{label}</div>
      <div className="graph-container">
        <img
          src={url}
          alt={`${label} latency graph for ${target.name}`}
          className="graph-img"
          draggable={false}
        />
        <div
          className="graph-drag-overlay"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        />
        {selectionStyle && <div className="drag-selection" style={selectionStyle} />}
      </div>
    </div>
  )
}

export default function GraphView({ target, onZoom }) {
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

  const now = Math.floor(Date.now() / 1000)

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
            startTs={now - RANGE_SECONDS[value]}
            endTs={now}
            onZoom={onZoom}
          />
        ))}
      </div>
    </div>
  )
}
