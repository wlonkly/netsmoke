import { useMemo, useState } from 'react'
import type { RecentMeasurement, TargetDetail as TargetDetailType, TreeTarget } from '../../lib/api'

type TargetDetailProps = {
  target: TargetDetailType | TreeTarget | null
}

const RANGE_OPTIONS = [
  { label: '30m', value: '30m' },
  { label: '6h', value: '6h' },
  { label: '1d', value: '1d' },
] as const

function hasRecentMeasurements(target: TargetDetailType | TreeTarget | null): target is TargetDetailType {
  return Boolean(target && 'recentMeasurements' in target)
}

export function TargetDetail({ target }: TargetDetailProps) {
  const [range, setRange] = useState<(typeof RANGE_OPTIONS)[number]['value']>('6h')

  const recentMeasurements = useMemo<RecentMeasurement[]>(() => {
    return hasRecentMeasurements(target) ? target.recentMeasurements : []
  }, [target])

  if (!target) {
    return (
      <section className="panel detail-panel empty-state">
        <h2>Select a target</h2>
        <p>Pick a host from the tree to see its latest status and graph preview.</p>
      </section>
    )
  }

  return (
    <section className="detail-panel">
      <header className="panel hero-panel">
        <div>
          <p className="eyebrow">Target</p>
          <h1>{target.name}</h1>
          <p className="muted">{target.path}</p>
        </div>
        <div className="status-grid">
          <article>
            <span className="metric-label">Host</span>
            <strong>{target.host}</strong>
          </article>
          <article>
            <span className="metric-label">Median RTT</span>
            <strong>
              {target.lastMeasurement.medianRttMs === null
                ? 'Pending'
                : `${target.lastMeasurement.medianRttMs.toFixed(1)} ms`}
            </strong>
          </article>
          <article>
            <span className="metric-label">Packet loss</span>
            <strong>{target.lastMeasurement.lossPct.toFixed(1)}%</strong>
          </article>
        </div>
      </header>

      <section className="panel graph-panel">
        <div className="panel-header graph-header-row">
          <span>Graph preview</span>
          <div className="range-selector">
            {RANGE_OPTIONS.map((option) => (
              <button
                key={option.value}
                className={range === option.value ? 'range-button active' : 'range-button'}
                onClick={() => setRange(option.value)}
                type="button"
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <div className="graph-frame">
          <img
            alt={`Smoke graph preview for ${target.name}`}
            className="graph-image"
            src={`/api/targets/${target.id}/graph.svg?range=${range}`}
          />
        </div>
      </section>

      <section className="panel recent-panel">
        <div className="panel-header">Recent rounds</div>
        {recentMeasurements.length > 0 ? (
          <div className="recent-table-wrapper">
            <table className="recent-table">
              <thead>
                <tr>
                  <th>Observed</th>
                  <th>Median RTT</th>
                  <th>Loss</th>
                  <th>Recv/Sent</th>
                </tr>
              </thead>
              <tbody>
                {recentMeasurements.map((measurement) => (
                  <tr key={measurement.observedAt}>
                    <td>{measurement.observedAt}</td>
                    <td>
                      {measurement.medianRttMs === null ? 'Pending' : `${measurement.medianRttMs.toFixed(1)} ms`}
                    </td>
                    <td>{measurement.lossPct.toFixed(1)}%</td>
                    <td>
                      {measurement.received}/{measurement.sent}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-subpanel">No measurements yet.</div>
        )}
      </section>
    </section>
  )
}
