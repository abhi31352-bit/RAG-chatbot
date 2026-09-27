import { describe, expect, it, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useDocuments } from './useDocuments'
import { documentService } from '../services/documentService'
import { resetDocumentStore, useDocumentStore } from '../stores/documentStore'
import { ApiError } from '../services/apiClient'
import type { Document } from '../types'

vi.mock('../services/documentService', () => ({
  documentService: {
    list: vi.fn(),
    upload: vi.fn(),
    remove: vi.fn(),
  },
}))

const list = vi.mocked(documentService.list)
const upload = vi.mocked(documentService.upload)
const remove = vi.mocked(documentService.remove)

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

beforeEach(() => {
  vi.clearAllMocks()
  resetDocumentStore()
  list.mockResolvedValue({ documents: [], total: 0 })
  upload.mockResolvedValue(doc())
  remove.mockResolvedValue(undefined)
})

describe('useDocuments loading', () => {
  it('loads the document list on mount', async () => {
    list.mockResolvedValue({ documents: [doc()], total: 1 })
    const { result } = renderHook(() => useDocuments())

    await waitFor(() => expect(result.current.documents).toHaveLength(1))
    expect(result.current.documents[0].filename).toBe('syllabus.txt')
    expect(result.current.isLoading).toBe(false)
  })

  it('reports a load failure', async () => {
    list.mockRejectedValue(new ApiError('Network Error', 'NETWORK_ERROR', 0))
    const { result } = renderHook(() => useDocuments())

    await waitFor(() => expect(result.current.error).toBe('Network Error'))
    expect(result.current.isLoading).toBe(false)
  })

  it('clears a previous error when reloaded', async () => {
    list.mockRejectedValueOnce(new Error('boom'))
    const { result } = renderHook(() => useDocuments())
    await waitFor(() => expect(result.current.error).toBe('boom'))

    list.mockResolvedValue({ documents: [], total: 0 })
    await act(async () => {
      await result.current.refresh()
    })

    expect(result.current.error).toBeNull()
  })
})

describe('useDocuments upload', () => {
  it('adds the uploaded document and reports it', async () => {
    const { result } = renderHook(() => useDocuments())
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    let returned: Document | null = null
    await act(async () => {
      returned = await result.current.upload(new File(['x'], 'syllabus.txt'))
    })

    expect(returned).toEqual(doc())
    expect(result.current.documents).toHaveLength(1)
    expect(result.current.notice).toBe('Indexed "syllabus.txt" as 2 chunks.')
  })

  it('phrases a single-chunk upload in the singular', async () => {
    // The notice quotes the filename the server recorded, not the one on the
    // File the browser handed over.
    upload.mockResolvedValue(doc({ chunk_count: 1, filename: 'a.md' }))
    const { result } = renderHook(() => useDocuments())
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.upload(new File(['x'], 'a.md'))
    })

    expect(result.current.notice).toBe('Indexed "a.md" as 1 chunk.')
  })

  it('moves from uploading to indexing once the bytes are sent', async () => {
    // The backend embeds inside the upload request, so a bar parked at 100%
    // with no explanation is indistinguishable from a hang.
    const phases: string[] = []
    upload.mockImplementation(async (_file, onProgress) => {
      onProgress?.(50)
      phases.push(useDocumentStore.getState().uploadPhase)
      onProgress?.(100)
      phases.push(useDocumentStore.getState().uploadPhase)
      return doc()
    })

    const { result } = renderHook(() => useDocuments())
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.upload(new File(['x'], 'a.txt'))
    })

    expect(phases).toEqual(['uploading', 'indexing'])
  })

  it('leaves the failed file out of the list and shows the reason', async () => {
    upload.mockRejectedValue(new ApiError('The index was built with local-hash-512', 'EMBEDDING_MISMATCH', 409))
    const { result } = renderHook(() => useDocuments())
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.upload(new File(['x'], 'a.txt'))
    })

    expect(result.current.documents).toHaveLength(0)
    expect(result.current.error).toContain('local-hash-512')
    expect(result.current.isUploading).toBe(false)
  })

  it('resets upload state even when the request fails', async () => {
    upload.mockRejectedValue(new Error('nope'))
    const { result } = renderHook(() => useDocuments())
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.upload(new File(['x'], 'a.txt'))
    })

    expect(result.current.uploadPhase).toBe('idle')
    expect(result.current.uploadProgress).toBe(0)
  })
})

describe('useDocuments delete', () => {
  it('removes the row only after the server confirms', async () => {
    list.mockResolvedValue({ documents: [doc()], total: 1 })
    const { result } = renderHook(() => useDocuments())
    await waitFor(() => expect(result.current.documents).toHaveLength(1))

    await act(async () => {
      await result.current.remove('doc_1')
    })

    expect(remove).toHaveBeenCalledWith('doc_1')
    expect(result.current.documents).toHaveLength(0)
    expect(result.current.notice).toContain('deleted')
  })

  it('keeps the row when the server rejects the delete', async () => {
    // Dropping the row anyway would show a document as gone while the server
    // still has it, and it would silently return on the next refresh.
    list.mockResolvedValue({ documents: [doc()], total: 1 })
    remove.mockRejectedValue(new ApiError('Document doc_1 was not found', 'DOCUMENT_NOT_FOUND', 404))
    const { result } = renderHook(() => useDocuments())
    await waitFor(() => expect(result.current.documents).toHaveLength(1))

    await act(async () => {
      await result.current.remove('doc_1')
    })

    expect(result.current.documents).toHaveLength(1)
    expect(result.current.error).toContain('not found')
    expect(result.current.deletingId).toBeNull()
  })

  it('marks the row being deleted', async () => {
    list.mockResolvedValue({ documents: [doc()], total: 1 })
    const { result } = renderHook(() => useDocuments())
    await waitFor(() => expect(result.current.documents).toHaveLength(1))

    let seen: string | null = null
    remove.mockImplementation(async () => {
      seen = useDocumentStore.getState().deletingId
      return undefined
    })

    await act(async () => {
      await result.current.remove('doc_1')
    })

    expect(seen).toBe('doc_1')
  })
})
