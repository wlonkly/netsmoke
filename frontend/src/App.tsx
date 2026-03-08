import { useEffect, useMemo, useState } from 'react'
import { TargetDetail } from './features/target/TargetDetail'
import { TargetTree } from './features/tree/TargetTree'
import { fetchTree, type TreeTarget } from './lib/api'

export function App() {
  const [targets, setTargets] = useState<TreeTarget[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchTree()
      .then((data) => {
        setTargets(data)
        setSelectedId(data[0]?.id ?? null)
      })
      .catch((err: Error) => {
        setError(err.message)
      })
  }, [])

  const selectedTarget = useMemo(
    () => targets.find((target) => target.id === selectedId) ?? null,
    [selectedId, targets],
  )

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">netsmoke</p>
          <h1>Network latency and packet loss</h1>
        </div>
        <p className="muted">FastAPI + React scaffold with SmokePing-style SVG rendering.</p>
      </header>
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="workspace">
        <TargetTree
          onSelect={(target) => setSelectedId(target.id)}
          selectedId={selectedId}
          targets={targets}
        />
        <TargetDetail target={selectedTarget} />
      </div>
    </main>
  )
}
