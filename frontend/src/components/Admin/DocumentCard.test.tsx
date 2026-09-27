import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DocumentCard } from './DocumentCard'
import { formatDate, formatSize } from './format'
import type { Document } from '../../types'

const DOC: Document = {
  id: 'doc_1',
  filename: 'syllabus.txt',
  file_type: 'txt',
  file_size: 2048,
  chunk_count: 3,
  status: 'processed',
  created_at: '2026-03-04T10:00:00Z',
}

function renderCard(overrides: Partial<Document> = {}, onDelete = vi.fn()) {
  render(<DocumentCard document={{ ...DOC, ...overrides }} onDelete={onDelete} />)
  return { onDelete }
}

describe('formatSize', () => {
  it('scales the unit to the size', () => {
    expect(formatSize(512)).toBe('512 B')
    expect(formatSize(2048)).toBe('2.0 KB')
    expect(formatSize(5 * 1024 * 1024)).toBe('5.0 MB')
  })

  it('reports an unusable size as a dash rather than NaN', () => {
    expect(formatSize(NaN)).toBe('—')
    expect(formatSize(-1)).toBe('—')
  })
})

describe('formatDate', () => {
  it('formats a real timestamp', () => {
    expect(formatDate('2026-03-04T10:00:00Z')).toMatch(/2026/)
  })

  it('does not print "Invalid Date" for an unparseable value', () => {
    expect(formatDate('not-a-date')).toBe('unknown date')
  })
})

describe('DocumentCard', () => {
  it('shows the filename, chunk count, size and status', () => {
    renderCard()
    expect(screen.getByText('syllabus.txt')).toBeInTheDocument()
    expect(screen.getByText('3 chunks')).toBeInTheDocument()
    expect(screen.getByText('2.0 KB')).toBeInTheDocument()
    expect(screen.getByText('indexed')).toBeInTheDocument()
  })

  it('labels a failed document', () => {
    renderCard({ status: 'failed' })
    expect(screen.getByText('failed')).toBeInTheDocument()
  })

  it('labels a still-processing document', () => {
    renderCard({ status: 'pending' })
    expect(screen.getByText('processing')).toBeInTheDocument()
  })

  it('asks for confirmation before deleting', async () => {
    // window.confirm is not implemented in jsdom, so using it here would make
    // this path untestable rather than merely unpolished.
    const user = userEvent.setup()
    const { onDelete } = renderCard()

    await user.click(screen.getByRole('button', { name: 'Delete syllabus.txt' }))

    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('Delete this document?')
    expect(dialog).toHaveTextContent('3 indexed chunks')
    expect(onDelete).not.toHaveBeenCalled()
  })

  it('deletes once confirmed', async () => {
    const user = userEvent.setup()
    const { onDelete } = renderCard()

    await user.click(screen.getByRole('button', { name: 'Delete syllabus.txt' }))
    await user.click(await screen.findByRole('button', { name: 'Delete' }))

    expect(onDelete).toHaveBeenCalledWith('doc_1')
  })

  it('closes without deleting when cancelled', async () => {
    const user = userEvent.setup()
    const { onDelete } = renderCard()

    await user.click(screen.getByRole('button', { name: 'Delete syllabus.txt' }))
    await user.click(await screen.findByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(onDelete).not.toHaveBeenCalled()
  })

  it('keeps the dialog open when the delete fails', async () => {
    // Closing on failure would tell the user the document is gone when the
    // server still has it, and it would reappear on the next refresh.
    const user = userEvent.setup()
    const { onDelete } = renderCard({}, vi.fn().mockResolvedValue(false))

    await user.click(screen.getByRole('button', { name: 'Delete syllabus.txt' }))
    await user.click(await screen.findByRole('button', { name: 'Delete' }))

    await waitFor(() => expect(onDelete).toHaveBeenCalled())
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('cancels on Escape', async () => {
    const user = userEvent.setup()
    renderCard()

    await user.click(screen.getByRole('button', { name: 'Delete syllabus.txt' }))
    await screen.findByRole('dialog')
    await user.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('disables the delete button while a delete is in flight', () => {
    render(<DocumentCard document={DOC} onDelete={vi.fn()} isDeleting />)
    expect(screen.getByRole('button', { name: 'Delete syllabus.txt' })).toBeDisabled()
  })
})
