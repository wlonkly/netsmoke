export type LastMeasurement = {
  observedAt: string
  medianRttMs: number | null
  lossPct: number
}

export type RecentMeasurement = {
  observedAt: string
  sent: number
  received: number
  lossPct: number
  medianRttMs: number | null
}

export type CollectorStatus = {
  enabled: boolean
  status: string
  lastStartedAt: string | null
  lastFinishedAt: string | null
  lastSuccessAt: string | null
  lastError: string | null
  lastErrorAt: string | null
  lastRoundTargetCount: number
  lastRoundPersistedCount: number
  lastRoundSummary: Array<{
    targetSlug: string
    sent: number
    received: number
    lossPct: number
    medianRttMs: number | null
  }>
}

export type TreeTarget = {
  id: string
  name: string
  path: string
  host: string
  lastMeasurement: LastMeasurement
}

export type TargetDetail = TreeTarget & {
  enabled: boolean
  recentMeasurements: RecentMeasurement[]
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

export async function fetchCollectorStatus(): Promise<CollectorStatus> {
  const response = await fetch('/api/collector/status')
  if (!response.ok) {
    throw new Error('Failed to fetch collector status')
  }

  return (await response.json()) as CollectorStatus
}

export async function fetchTargetDetail(targetId: string): Promise<TargetDetail> {
  const response = await fetch(`/api/targets/${targetId}`)
  if (!response.ok) {
    throw new Error('Failed to fetch target detail')
  }

  return (await response.json()) as TargetDetail
}
