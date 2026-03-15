import { useState, useEffect } from 'react'
import { graphUrlWindow } from '../api.js'

function tsToDatetimeLocal(ts) {
  const d = new Date(ts * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  )
}

function datetimeLocalToTs(s) {
  return Math.floor(new Date(s).getTime() / 1000)
}

export default function ZoomView({ target, startTs, endTs, onBack, onZoom }) {
  const [localStart, setLocalStart] = useState(startTs)
  const [localEnd, setLocalEnd] = useState(endTs)
  const [drag, setDrag] = useState(null)
  const [imgKey, setImgKey] = useState(0)

  // Sync local state when props change (e.g. further zoom-in from drag)
  useEffect(() => {
    setLocalStart(startTs)
    setLocalEnd(endTs)
    setImgKey((k) => k + 1)
  }, [startTs, endTs])

  function handleStartChange(e) {
    const ts = datetimeLocalToTs(e.target.value)
    if (!isNaN(ts)) {
      setLocalStart(ts)
      setImgKey((k) => k + 1)
    }
  }

  function handleEndChange(e) {
    const ts = datetimeLocalToTs(e.target.value)
    if (!isNaN(ts)) {
      setLocalEnd(ts)
      setImgKey((k) => k + 1)
    }
  }

  function handleZoomOut() {
    const center = (localStart + localEnd) / 2
    const half = localEnd - localStart
    onZoom(Math.floor(center - half), Math.floor(center + half))
  }

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

  function handleMouseUp() {
    if (!drag) return
    const { x0, x1, containerWidth } = drag
    setDrag(null)
    if (Math.abs(x1 - x0) < 5) return
    const left = Math.min(x0, x1)
    const right = Math.max(x0, x1)
    const selStart = Math.floor(localStart + (left / containerWidth) * (localEnd - localStart))
    const selEnd = Math.floor(localStart + (right / containerWidth) * (localEnd - localStart))
    onZoom(selStart, selEnd)
  }

  const selectionStyle = drag
    ? { left: Math.min(drag.x0, drag.x1), width: Math.abs(drag.x1 - drag.x0) }
    : null

  const imgUrl = graphUrlWindow(target.path, localStart, localEnd) + `&_k=${imgKey}`

  return (
    <div className="zoom-view">
      <div className="zoom-header">
        <div className="graph-title">
          <span className="graph-target-name">{target.name}</span>
          <span className="graph-target-host">{target.host}</span>
        </div>
        <div className="zoom-controls">
          <input
            type="datetime-local"
            className="zoom-time-input"
            value={tsToDatetimeLocal(localStart)}
            onChange={handleStartChange}
          />
          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>→</span>
          <input
            type="datetime-local"
            className="zoom-time-input"
            value={tsToDatetimeLocal(localEnd)}
            onChange={handleEndChange}
          />
          <button className="btn-zoom-out" onClick={handleZoomOut}>
            Zoom out
          </button>
          <button className="btn-back" onClick={onBack}>
            ← Back
          </button>
        </div>
      </div>

      <div className="graph-container">
        <img
          src={imgUrl}
          alt={`Zoomed latency graph for ${target.name}`}
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
