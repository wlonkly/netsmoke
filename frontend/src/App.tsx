import { useState, useEffect } from 'react'
import { fetchTargets } from './api'
import Sidebar from './components/Sidebar'
import GraphView from './components/GraphView'
import ZoomView from './components/ZoomView'
import type { TreeNode, TargetNode, ZoomState } from './types'

export default function App() {
  const [tree, setTree] = useState<TreeNode[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTarget, setActiveTarget] = useState<TargetNode | null>(null)
  const [zoomState, setZoomState] = useState<ZoomState | null>(null)

  useEffect(() => {
    fetchTargets()
      .then((data) => {
        setTree(data)
        setLoading(false)
        const first = findFirstTarget(data)
        if (first) setActiveTarget(first)
      })
      .catch((e: Error) => {
        setError(e.message)
        setLoading(false)
      })
  }, [])

  useEffect(() => {
    if (activeTarget) {
      document.title = `${activeTarget.name} — netsmoke`
    } else {
      document.title = 'netsmoke'
    }
  }, [activeTarget])

  function handleSelectTarget(target: TargetNode) {
    setActiveTarget(target)
    setZoomState(null)
  }

  function handleZoom(startTs: number, endTs: number) {
    if (!activeTarget) return
    setZoomState({ target: activeTarget, startTs, endTs })
  }

  function handleZoomFromZoom(startTs: number, endTs: number) {
    setZoomState((z) => (z ? { ...z, startTs, endTs } : z))
  }

  return (
    <div className="app">
      <Sidebar
        tree={tree}
        activePath={activeTarget?.path ?? null}
        onSelect={handleSelectTarget}
        loading={loading}
        error={error}
      />
      <main className="main-content">
        {zoomState ? (
          <ZoomView
            target={zoomState.target}
            startTs={zoomState.startTs}
            endTs={zoomState.endTs}
            onBack={() => setZoomState(null)}
            onZoom={handleZoomFromZoom}
          />
        ) : (
          <GraphView target={activeTarget} onZoom={handleZoom} />
        )}
      </main>
    </div>
  )
}

function findFirstTarget(nodes: TreeNode[]): TargetNode | null {
  for (const item of nodes) {
    if (item.type === 'target') return item
    if (item.type === 'folder') {
      const found = findFirstTarget(item.children)
      if (found) return found
    }
  }
  return null
}
