import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from '../App.jsx'
import { fetchTargets, fetchStats } from '../api.js'

// Keep graphUrl / graphUrlWindow as real implementations; only mock the fetch calls.
vi.mock('../api.js', async (importActual) => {
  const actual = await importActual()
  return { ...actual, fetchTargets: vi.fn(), fetchStats: vi.fn() }
})

const TARGET = { type: 'target', path: '8.8.8.8', name: 'Google DNS', host: '8.8.8.8' }
const TARGET2 = { type: 'target', path: '1.1.1.1', name: 'Cloudflare DNS', host: '1.1.1.1' }
const FOLDER_TREE = [{
  type: 'folder', path: 'CDNs', name: 'CDNs',
  children: [{ type: 'target', path: 'CDNs/Cloudflare', name: 'Cloudflare', host: '1.1.1.1' }],
}]

beforeEach(() => {
  vi.resetAllMocks()
  fetchStats.mockResolvedValue({ median_ms: 12.3, loss_pct: 0, sample_count: 10 })
})

// Trigger a drag on the first .graph-drag-overlay large enough to fire onZoom.
function dragOnFirstOverlay(container) {
  const overlay = container.querySelector('.graph-drag-overlay')
  overlay.getBoundingClientRect = vi.fn().mockReturnValue({
    left: 0, width: 500, top: 0, right: 500, bottom: 100, height: 100,
  })
  fireEvent.mouseDown(overlay, { clientX: 50 })
  fireEvent.mouseMove(overlay, { clientX: 450 })
  fireEvent.mouseUp(overlay)
}

describe('App initial load', () => {
  it('auto-selects the first flat target', async () => {
    fetchTargets.mockResolvedValue([TARGET])
    render(<App />)
    // Graph header shows the selected target name
    expect(await screen.findByText('Google DNS', { selector: '.graph-target-name' })).toBeInTheDocument()
  })

  it('auto-selects the first target inside a folder', async () => {
    fetchTargets.mockResolvedValue(FOLDER_TREE)
    render(<App />)
    expect(await screen.findByText('Cloudflare', { selector: '.graph-target-name' })).toBeInTheDocument()
  })

  it('shows an error in the sidebar when the fetch fails', async () => {
    fetchTargets.mockRejectedValue(new Error('timeout'))
    render(<App />)
    expect(await screen.findByText(/timeout/)).toBeInTheDocument()
  })

  it('renders GraphView (not ZoomView) on initial load', async () => {
    fetchTargets.mockResolvedValue([TARGET])
    render(<App />)
    await screen.findByText('Google DNS', { selector: '.graph-target-name' })
    expect(screen.queryByRole('button', { name: /Back/ })).not.toBeInTheDocument()
  })
})

describe('App zoom state transitions', () => {
  async function renderAndZoom() {
    fetchTargets.mockResolvedValue([TARGET])
    const utils = render(<App />)
    await screen.findByText('Google DNS', { selector: '.graph-target-name' })
    dragOnFirstOverlay(utils.container)
    return utils
  }

  it('shows ZoomView after dragging on a graph panel', async () => {
    await renderAndZoom()
    expect(screen.getByRole('button', { name: /Back/ })).toBeInTheDocument()
  })

  it('returns to GraphView when the Back button is clicked', async () => {
    await renderAndZoom()
    fireEvent.click(screen.getByRole('button', { name: /Back/ }))
    // GraphView renders 4 panels; ZoomView renders 1
    await waitFor(() => expect(screen.getAllByRole('img')).toHaveLength(4))
  })

  it('clears zoom state when a sidebar target is selected', async () => {
    fetchTargets.mockResolvedValue([TARGET, TARGET2])
    const { container } = render(<App />)
    await screen.findByText('Google DNS', { selector: '.graph-target-name' })
    dragOnFirstOverlay(container)
    expect(screen.getByRole('button', { name: /Back/ })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Cloudflare DNS' }))
    // Wait for the new target to become active (flushes the fetchStats promise)
    await screen.findByText('Cloudflare DNS', { selector: '.graph-target-name' })
    expect(screen.queryByRole('button', { name: /Back/ })).not.toBeInTheDocument()
  })

  it('keeps the same target when re-zooming from ZoomView', async () => {
    const { container } = await renderAndZoom()
    // We're now in ZoomView showing Google DNS
    expect(screen.getByText('Google DNS', { selector: '.graph-target-name' })).toBeInTheDocument()

    // Drag again inside ZoomView to zoom further in
    dragOnFirstOverlay(container)

    // Still ZoomView, still same target
    expect(screen.getByRole('button', { name: /Back/ })).toBeInTheDocument()
    expect(screen.getByText('Google DNS', { selector: '.graph-target-name' })).toBeInTheDocument()
  })
})
