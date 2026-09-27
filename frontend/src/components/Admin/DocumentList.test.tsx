import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DocumentList } from './DocumentList'
import type { Document } from '../../types'

function doc(overrides: Partial<Document> = {}): Document {
  return {
    id: 'doc_1',
    filename: 'syllabus.txt',
    file_type: 'txt',
    file_size: 100,
    chunk_count: 2,
    status: 'processed',
    created_at: '2026-03-04T10:00:00Z',
    ...overrides,
  }
}

describe('DocumentList', () => {
  it('invites the first upload when empty', () => {
    render(<DocumentList documents={[]} onDelete={vi.fn()} />)
    expect(screen.getByText('No documents uploaded yet.')).toBeInTheDocument()
  })

  it('counts the documents without pluralising one', () => {
    const { rerender } = render(<DocumentList documents={[doc()]} onDelete={vi.fn()} />)
    expect(screen.getByText('1 document uploaded')).toBeInTheDocument()

    rerender(<DocumentList documents={[doc(), doc({ id: 'doc_2' })]} onDelete={vi.fn()} />)
    expect(screen.getByText('2 documents uploaded')).toBeInTheDocument()
  })

  it('renders a card per document', () => {
    render(
      <DocumentList
        documents={[doc(), doc({ id: 'doc_2', filename: 'lecture.md', file_type: 'md' })]}
        onDelete={vi.fn()}
      />,
    )
    expect(screen.getByText('syllabus.txt')).toBeInTheDocument()
    expect(screen.getByText('lecture.md')).toBeInTheDocument()
  })

  it('marks only the document being deleted as busy', () => {
    render(
      <DocumentList
        documents={[doc(), doc({ id: 'doc_2', filename: 'lecture.md' })]}
        onDelete={vi.fn()}
        deletingId="doc_2"
      />,
    )
    expect(screen.getByRole('button', { name: 'Delete syllabus.txt' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Delete lecture.md' })).toBeDisabled()
  })
})
