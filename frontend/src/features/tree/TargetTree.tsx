import type { TreeTarget } from '../../lib/api'

type TargetTreeProps = {
  targets: TreeTarget[]
  selectedId: string | null
  onSelect: (target: TreeTarget) => void
}

export function TargetTree({ targets, selectedId, onSelect }: TargetTreeProps) {
  return (
    <aside className="panel sidebar">
      <div className="panel-header">Targets</div>
      <ul className="target-list">
        {targets.map((target) => (
          <li key={target.id}>
            <button
              className={target.id === selectedId ? 'target-button active' : 'target-button'}
              onClick={() => onSelect(target)}
              type="button"
            >
              <span className="target-name">{target.name}</span>
              <span className="target-path">{target.path}</span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
