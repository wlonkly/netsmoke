export type TreeTarget = {
  id: string
  name: string
  path: string
  host: string
  lastMeasurement: {
    observedAt: string
    medianRttMs: number | null
    lossPct: number
  }
}

export async function fetchTree(): Promise<TreeTarget[]> {
  const response = await fetch('/api/tree')
  if (!response.ok) {
    throw new Error('Failed to fetch tree')
  }

  const payload = (await response.json()) as { targets: TreeTarget[] }
  return payload.targets
}
