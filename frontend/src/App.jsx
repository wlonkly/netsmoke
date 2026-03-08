import { useState, useEffect } from 'react'
import { fetchTargets } from './api.js'
import Sidebar from './components/Sidebar.jsx'
import GraphView from './components/GraphView.jsx'

export default function App() {
  const [tree, setTree] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTarget, setActiveTarget] = useState(null)

  useEffect(() => {
    fetchTargets()
      .then((data) => {
        setTree(data)
        setLoading(false)
        // Auto-select first target
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

  return (
    <div className="app">
      <Sidebar
        tree={tree}
        activePath={activeTarget?.path}
        onSelect={setActiveTarget}
        loading={loading}
        error={error}
      />
      <main className="main-content">
        <GraphView target={activeTarget} />
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
