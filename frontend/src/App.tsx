import { useCallback, useEffect, useMemo, useState } from 'react'
import { TargetDetail as TargetDetailPanel } from './features/target/TargetDetail'
import { TargetTree } from './features/tree/TargetTree'
import {
  fetchCollectorStatus,
  fetchTargetDetail,
  fetchTree,
  type CollectorStatus,
  type TargetDetail,
  type TreeNode,
  type TreeTarget,
} from './lib/api'

const REFRESH_INTERVAL_MS = 30_000

export function App() {
  const [targets, setTargets] = useState<TreeTarget[]>([])
  const [tree, setTree] = useState<TreeNode[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedTarget, setSelectedTarget] = useState<TargetDetail | null>(null)
  const [collectorStatus, setCollectorStatus] = useState<CollectorStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [treeData, statusData] = await Promise.all([fetchTree(), fetchCollectorStatus()])
      setTargets(treeData.targets)
      setTree(treeData.tree)
      setCollectorStatus(statusData)
      const nextSelectedId = selectedId ?? treeData.targets[0]?.id ?? null
      setSelectedId(nextSelectedId)
      if (nextSelectedId) {
        setSelectedTarget(await fetchTargetDetail(nextSelectedId))
      } else {
        setSelectedTarget(null)
      }
      setError(null)
    } catch (err) {
      setError((err as Error).message)
    }
  }, [selectedId])

  useEffect(() => {
    void refresh()
    const intervalId = window.setInterval(() => {
      void refresh()
    }, REFRESH_INTERVAL_MS)
    return () => window.clearInterval(intervalId)
  }, [refresh])

  const selectedTreeTarget = useMemo(
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
      {collectorStatus ? (
        <section className="panel collector-panel">
          <div>
            <p className="eyebrow">Collector</p>
            <strong className={`collector-state collector-state-${collectorStatus.status}`}>{collectorStatus.status}</strong>
          </div>
          <div className="collector-metadata">
            <span>Enabled: {collectorStatus.enabled ? 'yes' : 'no'}</span>
            <span>Last success: {collectorStatus.lastSuccessAt ?? 'never'}</span>
            <span>Last error: {collectorStatus.lastError ?? 'none'}</span>
          </div>
        </section>
      ) : null}
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="workspace">
        <TargetTree
          onSelect={(target) => {
            setSelectedId(target.id)
            void fetchTargetDetail(target.id).then(setSelectedTarget).catch((err: Error) => setError(err.message))
          }}
          selectedId={selectedId}
          tree={tree}
        />
        <TargetDetailPanel target={selectedTarget ?? selectedTreeTarget} />
      </div>
    </main>
  )
}
