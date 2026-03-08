import type { TreeNode, TreeTarget } from '../../lib/api'

type TargetTreeProps = {
  tree: TreeNode[]
  selectedId: string | null
  onSelect: (target: TreeTarget) => void
}

export function TargetTree({ tree, selectedId, onSelect }: TargetTreeProps) {
  return (
    <aside className="panel sidebar">
      <div className="panel-header">Targets</div>
      <div className="tree-root">
        {tree.map((node) => (
          <TreeBranch key={node.id} node={node} onSelect={onSelect} selectedId={selectedId} />
        ))}
      </div>
    </aside>
  )
}

type TreeBranchProps = {
  node: TreeNode
  selectedId: string | null
  onSelect: (target: TreeTarget) => void
}

function TreeBranch({ node, selectedId, onSelect }: TreeBranchProps) {
  if (node.type === 'folder') {
    return (
      <section className="tree-folder">
        <div className="tree-folder-label">{node.name}</div>
        <div className="tree-folder-children">
          {node.children.map((child) => (
            <TreeBranch key={child.id} node={child} onSelect={onSelect} selectedId={selectedId} />
          ))}
        </div>
      </section>
    )
  }

  return (
    <button
      className={node.id === selectedId ? 'target-button active' : 'target-button'}
      onClick={() => onSelect(node)}
      type="button"
    >
      <span className="target-name">{node.name}</span>
      <span className="target-path">{node.host}</span>
    </button>
  )
}
