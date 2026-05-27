import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Sidebar from '../components/Sidebar'
import type { TargetNode, FolderNode } from '../types'

const T1: TargetNode = { type: 'target', path: '8.8.8.8',  name: 'Google DNS', host: '8.8.8.8' }
const T2: TargetNode = { type: 'target', path: '1.1.1.1',  name: 'Cloudflare DNS', host: '1.1.1.1' }
const FOLDER: FolderNode = {
  type: 'folder', path: 'CDNs', name: 'CDNs',
  children: [{ type: 'target', path: 'CDNs/Cloudflare', name: 'Cloudflare', host: '1.1.1.1' }],
}

describe('Sidebar loading / error / empty states', () => {
  it('shows loading indicator', () => {
    render(<Sidebar loading={true} tree={null} activePath={null} onSelect={vi.fn()} />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows error message', () => {
    render(<Sidebar loading={false} error="Network error" tree={null} activePath={null} onSelect={vi.fn()} />)
    expect(screen.getByText(/Network error/)).toBeInTheDocument()
  })

  it('shows empty state when tree is empty', () => {
    render(<Sidebar loading={false} tree={[]} activePath={null} onSelect={vi.fn()} />)
    expect(screen.getByText('No targets')).toBeInTheDocument()
  })
})

describe('Sidebar target rendering', () => {
  it('renders a flat list of targets', () => {
    render(<Sidebar loading={false} tree={[T1, T2]} activePath={null} onSelect={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Google DNS' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cloudflare DNS' })).toBeInTheDocument()
  })

  it('applies .active to the active target only', () => {
    render(<Sidebar loading={false} tree={[T1, T2]} activePath="8.8.8.8" onSelect={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Google DNS' })).toHaveClass('active')
    expect(screen.getByRole('button', { name: 'Cloudflare DNS' })).not.toHaveClass('active')
  })

  it('calls onSelect with the node when a target is clicked', () => {
    const onSelect = vi.fn()
    render(<Sidebar loading={false} tree={[T1]} activePath={null} onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('button', { name: 'Google DNS' }))
    expect(onSelect).toHaveBeenCalledWith(T1)
  })
})

describe('Sidebar folder expand / collapse', () => {
  it('renders folder children visible by default', () => {
    render(<Sidebar loading={false} tree={[FOLDER]} activePath={null} onSelect={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Cloudflare' })).toBeInTheDocument()
  })

  it('hides children when the folder button is clicked', () => {
    render(<Sidebar loading={false} tree={[FOLDER]} activePath={null} onSelect={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /CDNs/ }))
    expect(screen.queryByRole('button', { name: 'Cloudflare' })).not.toBeInTheDocument()
  })

  it('re-expands the folder on a second click', () => {
    render(<Sidebar loading={false} tree={[FOLDER]} activePath={null} onSelect={vi.fn()} />)
    const folderBtn = screen.getByRole('button', { name: /CDNs/ })
    fireEvent.click(folderBtn)
    fireEvent.click(folderBtn)
    expect(screen.getByRole('button', { name: 'Cloudflare' })).toBeInTheDocument()
  })
})
