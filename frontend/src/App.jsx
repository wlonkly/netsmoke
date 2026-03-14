import { useState, useEffect } from 'react'
import { fetchTargets } from './api.js'
import Sidebar from './components/Sidebar.jsx'
import GraphView from './components/GraphView.jsx'
import ZoomView from './components/ZoomView.jsx'

export default function App() {
  const [tree, setTree] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTarget, setActiveTarget] = useState(null)
  const [zoomState, setZoomState] = useState(null) // { target, startTs, endTs } | null

  useEffect(() => {
    fetchTargets()
      .then((data) => {
        setTree(data)
        setLoading(false)
        const first = findFirstTarget(data)
        if (first) setActiveTarget(first)
      })
      .catch((e) => {
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

  function handleSelectTarget(target) {
    setActiveTarget(target)
    setZoomState(null)
  }

  function handleZoom(startTs, endTs) {
    setZoomState({ target: activeTarget, startTs, endTs })
  }

  function handleZoomFromZoom(startTs, endTs) {
    setZoomState((z) => ({ ...z, startTs, endTs }))
  }

  return (
    <div className="app">
      <Sidebar
        tree={tree}
        activePath={activeTarget?.path}
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

function findFirstTarget(items) {
  for (const item of items) {
    if (item.type === 'target') return item
    if (item.type === 'folder') {
      const found = findFirstTarget(item.children)
      if (found) return found
    }
  }
  return null
}
