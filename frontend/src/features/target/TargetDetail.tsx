import type { TreeTarget } from '../../lib/api'

type TargetDetailProps = {
  target: TreeTarget | null
}

export function TargetDetail({ target }: TargetDetailProps) {
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
        <div className="panel-header">Graph preview</div>
        <div className="graph-frame">
          <img
            alt={`Smoke graph preview for ${target.name}`}
            className="graph-image"
            src={`/api/targets/${target.id}/graph.svg?range=6h`}
          />
        </div>
      </section>
    </section>
  )
}
