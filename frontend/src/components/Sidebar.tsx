import { useState } from 'react'
import type { TreeNode, FolderNode, TargetNode } from '../types'

interface FolderItemProps {
  node: FolderNode
  activePath: string | null
  onSelect: (node: TargetNode) => void
  depth?: number
}

interface TargetItemProps {
  node: TargetNode
  activePath: string | null
  onSelect: (node: TargetNode) => void
  depth?: number
}

function FolderItem({ node, activePath, onSelect, depth = 0 }: FolderItemProps) {
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
              <FolderItem
                key={child.path}
                node={child}
                activePath={activePath}
                onSelect={onSelect}
                depth={depth + 1}
              />
            ) : (
              <TargetItem
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

function TargetItem({ node, activePath, onSelect, depth = 0 }: TargetItemProps) {
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

interface SidebarProps {
  tree: TreeNode[] | null
  activePath: string | null
  onSelect: (node: TargetNode) => void
  loading: boolean
  error?: string | null
}

export default function Sidebar({ tree, activePath, onSelect, loading, error }: SidebarProps) {
  if (loading) return <div className="sidebar-status">Loading...</div>
  if (error) return <div className="sidebar-status sidebar-error">Error: {error}</div>
  if (!tree || tree.length === 0) return <div className="sidebar-status">No targets</div>

  return (
    <nav className="sidebar">
      <div className="sidebar-header">netsmoke</div>
      <div className="sidebar-tree">
        {tree.map((node) =>
          node.type === 'folder' ? (
            <FolderItem
              key={node.path}
              node={node}
              activePath={activePath}
              onSelect={onSelect}
            />
          ) : (
            <TargetItem
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
