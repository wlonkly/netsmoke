import { describe, it, expect, vi, beforeEach } from 'vitest'
import { graphUrl, graphUrlWindow, fetchTargets, fetchStats } from '../api.js'

describe('graphUrl', () => {
  it('builds a simple target URL with default range', () => {
    expect(graphUrl('8.8.8.8')).toBe('/api/graph/8.8.8.8?range=3h')
  })

  it('respects an explicit range', () => {
    expect(graphUrl('8.8.8.8', '24h')).toBe('/api/graph/8.8.8.8?range=24h')
  })

  it('percent-encodes special characters in target path segments', () => {
    expect(graphUrl('CDNs/Cloudflare')).toBe('/api/graph/CDNs/Cloudflare?range=3h')
    expect(graphUrl('My Hosts/host.example.com')).toBe(
      '/api/graph/My%20Hosts/host.example.com?range=3h'
    )
  })
})

describe('graphUrlWindow', () => {
  it('builds a window URL with start/end timestamps', () => {
    expect(graphUrlWindow('CDNs/Cloudflare', 1000, 2000)).toBe(
      '/api/graph/CDNs/Cloudflare?start=1000&end=2000'
    )
  })
})

describe('fetchTargets', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('returns parsed JSON on success', async () => {
    const targets = [{ path: '8.8.8.8', name: '8.8.8.8' }]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(targets),
    }))

    const result = await fetchTargets()
    expect(result).toEqual(targets)
    expect(fetch).toHaveBeenCalledWith('/api/targets')
  })

  it('throws on non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    await expect(fetchTargets()).rejects.toThrow('503')
  })
})

describe('fetchStats', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('calls the correct URL with default window', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ median: 12.3 }),
    }))

    await fetchStats('CDNs/Cloudflare')
    expect(fetch).toHaveBeenCalledWith('/api/targets/CDNs/Cloudflare/stats?window=300')
  })
})
