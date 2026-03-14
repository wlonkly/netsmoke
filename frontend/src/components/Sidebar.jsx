import { useState } from 'react'

function FolderNode({ node, activePath, onSelect, depth = 0 }) {
  const [open, setOpen] = useState(true)

  return (
    <div className="sidebar-folder">
      <button
        className="sidebar-folder-btn"
        onClick={() => setOpen((o) => !o)}
        style={{ paddingLeft: `${depth * 14 + 8}px` }}
      >
        <span className="folder-arrow">{open ? '▾' : '▸'}</span>
        {node.name}
      </button>
      {open && (
        <div className="folder-children">
          {node.children.map((child) =>
            child.type === 'folder' ? (
              <FolderNode
                key={child.path}
                node={child}
                activePath={activePath}
                onSelect={onSelect}
                depth={depth + 1}
              />
            ) : (
              <TargetNode
                key={child.path}
                node={child}
                activePath={activePath}
                onSelect={onSelect}
                depth={depth + 1}
              />
            )
          )}
        </div>
      )}
    </div>
  )
}

function TargetNode({ node, activePath, onSelect, depth = 0 }) {
  const isActive = activePath === node.path
  return (
    <button
      className={`sidebar-target-btn${isActive ? ' active' : ''}`}
      style={{ paddingLeft: `${depth * 14 + 8}px` }}
      onClick={() => onSelect(node)}
    >
      {node.name}
    </button>
  )
}

export default function Sidebar({ tree, activePath, onSelect, loading, error }) {
  if (loading) return <div className="sidebar-status">Loading...</div>
  if (error) return <div className="sidebar-status sidebar-error">Error: {error}</div>
  if (!tree || tree.length === 0) return <div className="sidebar-status">No targets</div>

  return (
    <nav className="sidebar">
      <div className="sidebar-header">netsmoke</div>
      <div className="sidebar-tree">
        {tree.map((node) =>
          node.type === 'folder' ? (
            <FolderNode
              key={node.path}
              node={node}
              activePath={activePath}
              onSelect={onSelect}
            />
          ) : (
            <TargetNode
              key={node.path}
              node={node}
              activePath={activePath}
              onSelect={onSelect}
            />
          )
        )}
      </div>
    </nav>
  )
}
