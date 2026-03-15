export interface TargetNode {
  type: 'target'
  name: string
  host: string
  path: string
}

export interface FolderNode {
  type: 'folder'
  name: string
  path: string
  children: TreeNode[]
}

export type TreeNode = TargetNode | FolderNode

export interface Stats {
  median_ms: number | null
  loss_pct: number | null
  sample_count: number
}

export interface ZoomState {
  target: TargetNode
  startTs: number
  endTs: number
}

export type TimeRange = '3h' | '2d' | '1mo' | '1y'
