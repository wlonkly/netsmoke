import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ZoomView from '../components/ZoomView'
import type { TargetNode } from '../types'

const TARGET: TargetNode = { type: 'target', path: 'CDNs/Cloudflare', name: 'Cloudflare', host: '1.1.1.1' }

interface RenderZoomOptions {
  startTs?: number
  endTs?: number
  onBack?: () => void
  onZoom?: (startTs: number, endTs: number) => void
}

function renderZoom({ startTs = 1000, endTs = 2000, onBack, onZoom }: RenderZoomOptions = {}) {
  onBack = onBack ?? vi.fn()
  onZoom = onZoom ?? vi.fn()
  const result = render(
    <ZoomView target={TARGET} startTs={startTs} endTs={endTs} onBack={onBack} onZoom={onZoom} />
  )
  return { ...result, onBack, onZoom }
}

// Mock getBoundingClientRect on the drag overlay so containerWidth is non-zero.
function mockOverlay(container: HTMLElement, width = 500) {
  const overlay = container.querySelector('.graph-drag-overlay') as HTMLElement
  overlay.getBoundingClientRect = vi.fn().mockReturnValue({
    left: 0, width, top: 0, right: width, bottom: 100, height: 100,
  })
  return overlay
}

describe('ZoomView rendering', () => {
  it('shows target name and host', () => {
    renderZoom()
    expect(screen.getByText('Cloudflare')).toBeInTheDocument()
    expect(screen.getByText('1.1.1.1')).toBeInTheDocument()
  })

  it('renders a graph image with the windowed URL', () => {
    const { container } = renderZoom({ startTs: 1000, endTs: 2000 })
    const img = container.querySelector('img')
    expect(img?.getAttribute('src')).toMatch(/start=1000/)
    expect(img?.getAttribute('src')).toMatch(/end=2000/)
  })
})

describe('ZoomView back button', () => {
  it('calls onBack when clicked', () => {
    const { onBack } = renderZoom()
    fireEvent.click(screen.getByRole('button', { name: /Back/ }))
    expect(onBack).toHaveBeenCalledOnce()
  })
})

describe('ZoomView zoom-out', () => {
  // handleZoomOut: center = (start + end) / 2, half = end - start
  // new range: [floor(center - half), floor(center + half)]

  it('doubles the window centered on the midpoint', () => {
    // start=1000, end=3000 → center=2000, half=2000 → [0, 4000]
    const { onZoom } = renderZoom({ startTs: 1000, endTs: 3000 })
    fireEvent.click(screen.getByRole('button', { name: /Zoom out/ }))
    expect(onZoom).toHaveBeenCalledWith(0, 4000)
  })

  it('works when the window is not centered on zero', () => {
    // start=1000, end=2000 → center=1500, half=1000 → [500, 2500]
    const { onZoom } = renderZoom({ startTs: 1000, endTs: 2000 })
    fireEvent.click(screen.getByRole('button', { name: /Zoom out/ }))
    expect(onZoom).toHaveBeenCalledWith(500, 2500)
  })
})

describe('ZoomView drag-to-zoom', () => {
  // Timestamp math (start=1000, end=2000, width=500):
  //   selStart = floor(start + (left  / width) * duration)
  //   selEnd   = floor(start + (right / width) * duration)

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('calls onZoom with correctly mapped timestamps', () => {
    // drag x=100→300: selStart=floor(1000+(100/500)*1000)=1200, selEnd=1600
    const { container, onZoom } = renderZoom({ startTs: 1000, endTs: 2000 })
    const overlay = mockOverlay(container)
    fireEvent.mouseDown(overlay, { clientX: 100 })
    fireEvent.mouseMove(overlay, { clientX: 300 })
    fireEvent.mouseUp(overlay)
    expect(onZoom).toHaveBeenCalledWith(1200, 1600)
  })

  it('normalizes right-to-left drags to the same result', () => {
    const { container, onZoom } = renderZoom({ startTs: 1000, endTs: 2000 })
    const overlay = mockOverlay(container)
    fireEvent.mouseDown(overlay, { clientX: 300 })
    fireEvent.mouseMove(overlay, { clientX: 100 })
    fireEvent.mouseUp(overlay)
    expect(onZoom).toHaveBeenCalledWith(1200, 1600)
  })

  it('ignores drags smaller than 5px', () => {
    const { container, onZoom } = renderZoom({ startTs: 1000, endTs: 2000 })
    const overlay = mockOverlay(container)
    fireEvent.mouseDown(overlay, { clientX: 100 })
    fireEvent.mouseMove(overlay, { clientX: 103 })
    fireEvent.mouseUp(overlay)
    expect(onZoom).not.toHaveBeenCalled()
  })

  it('clamps mouse x to container bounds', () => {
    // drag x=0→700 with width=500: x1 clamped to 500 → selEnd = full endTs
    const { container, onZoom } = renderZoom({ startTs: 1000, endTs: 2000 })
    const overlay = mockOverlay(container)
    fireEvent.mouseDown(overlay, { clientX: 0 })
    fireEvent.mouseMove(overlay, { clientX: 700 })
    fireEvent.mouseUp(overlay)
    expect(onZoom).toHaveBeenCalledWith(1000, 2000)
  })

  it('cancels on mouseLeave', () => {
    // mouseLeave triggers the same handler as mouseUp
    const { container, onZoom } = renderZoom({ startTs: 1000, endTs: 2000 })
    const overlay = mockOverlay(container)
    fireEvent.mouseDown(overlay, { clientX: 100 })
    fireEvent.mouseMove(overlay, { clientX: 300 })
    fireEvent.mouseLeave(overlay)
    expect(onZoom).toHaveBeenCalledWith(1200, 1600)
  })
})
