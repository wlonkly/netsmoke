const BASE = ''  // proxied by Vite dev server; empty for prod same-origin

// Encode each path segment but preserve '/' separators so FastAPI's `path`
// converter can match routes like /api/graph/{target_path:path}
function encodePath(p) {
  return p.split('/').map(encodeURIComponent).join('/')
}

export async function fetchTargets() {
  const res = await fetch(`${BASE}/api/targets`)
  if (!res.ok) throw new Error(`Failed to fetch targets: ${res.status}`)
  return res.json()
}

export function graphUrl(targetPath, range = '3h') {
  return `${BASE}/api/graph/${encodePath(targetPath)}?range=${range}`
}

export function graphUrlWindow(targetPath, startTs, endTs) {
  return `${BASE}/api/graph/${encodePath(targetPath)}?start=${startTs}&end=${endTs}`
}

export async function fetchStats(targetPath, window = 300) {
  const res = await fetch(
    `${BASE}/api/targets/${encodePath(targetPath)}/stats?window=${window}`
  )
  if (!res.ok) throw new Error(`Failed to fetch stats: ${res.status}`)
  return res.json()
}
