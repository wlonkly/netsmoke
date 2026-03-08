export type LastMeasurement = {
  observedAt: string
  medianRttMs: number | null
  lossPct: number
}

export type TreeTarget = {
  id: string
  name: string
  path: string
  host: string
  lastMeasurement: LastMeasurement
}

export type TreeNode =
  | {
      id: string
      name: string
      type: 'folder'
      path: string
      children: TreeNode[]
    }
  | {
      id: string
      name: string
      type: 'host'
      path: string
      host: string
      lastMeasurement: LastMeasurement
    }

export async function fetchTree(): Promise<{ tree: TreeNode[]; targets: TreeTarget[] }> {
  const response = await fetch('/api/tree')
  if (!response.ok) {
    throw new Error('Failed to fetch tree')
  }

  return (await response.json()) as { tree: TreeNode[]; targets: TreeTarget[] }
}
