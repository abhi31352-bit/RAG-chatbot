import { describe, expect, it, vi } from 'vitest'
import { documentService } from './documentService'
import { apiClient, ApiError } from './apiClient'
import type { Document, DocumentListResponse, IndexStats } from '../types'

const DOC: Document = {
  id: 'doc_1',
  filename: 'syllabus.txt',
  file_type: 'txt',
  file_size: 100,
  chunk_count: 2,
  status: 'processed',
  created_at: '2026-03-04T10:00:00Z',
}

describe('documentService.upload', () => {
  it('sends multipart data without a Content-Type the browser cannot fill in', async () => {
    // Regression: apiClient sets a default `Content-Type: application/json`,
    // and axios merges instance headers into every request, so that default
    // reached the upload. With a Content-Type already present the browser
    // will NOT generate a multipart boundary, and the server answers 422
    // `{"loc":["body","file"],"msg":"Field required"}` -- which reads like a
    // missing form field rather than a broken header, and breaks upload
    // entirely.
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: DOC } as never)

    await documentService.upload(new File(['hello'], 'syllabus.txt', { type: 'text/plain' }))

    const [, body, config] = spy.mock.calls[0] as [string, FormData, Record<string, unknown>]
    expect(body).toBeInstanceOf(FormData)
    expect(config.headers).toEqual({ 'Content-Type': undefined })
    // Naming the multipart type outright is the other tempting fix and it is
    // wrong: that literal value is sent with no boundary.
    expect(config.headers).not.toEqual({ 'Content-Type': 'multipart/form-data' })
  })

  it('reports progress as a percentage when the total is known', async () => {
    vi.spyOn(apiClient, 'post').mockImplementation(async (_url, _body, config) => {
      const onProgress = (config as { onUploadProgress: (e: unknown) => void }).onUploadProgress
      onProgress({ loaded: 25, total: 100 })
      onProgress({ loaded: 100, total: 100 })
      return { data: DOC } as never
    })

    const seen: number[] = []
    await documentService.upload(new File(['x'], 'a.txt'), (p) => seen.push(p))

    expect(seen).toEqual([25, 100])
  })

  it('never divides by an unknown total', async () => {
    vi.spyOn(apiClient, 'post').mockImplementation(async (_url, _body, config) => {
      const onProgress = (config as { onUploadProgress: (e: unknown) => void }).onUploadProgress
      // A chunked body reports total === 0.
      onProgress({ loaded: 0, total: 0 })
      onProgress({ loaded: 512, total: 0 })
      return { data: DOC } as never
    })

    const seen: number[] = []
    await documentService.upload(new File(['x'], 'a.txt'), (p) => seen.push(p))

    expect(seen).not.toContain(NaN)
    expect(seen.every((p) => Number.isFinite(p))).toBe(true)
  })

  it('lets the ApiError from the interceptor reach the caller', async () => {
    // The admin panel renders ApiError.message, which is the only place the
    // backend's real reason (FILE_TOO_LARGE, EMBEDDING_MISMATCH, ...) appears
    // at all, so it must not be flattened into "Request failed with status".
    const failure = new ApiError('File exceeds the 50MB limit', 'FILE_TOO_LARGE', 413)
    vi.spyOn(apiClient, 'post').mockRejectedValue(failure)

    await expect(documentService.upload(new File(['x'], 'a.txt'))).rejects.toBe(failure)
  })
})

describe('documentService.list', () => {
  it('requests the trailing-slash path to avoid a redirect', async () => {
    const payload: DocumentListResponse = { documents: [DOC], total: 1 }
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: payload } as never)

    await expect(documentService.list()).resolves.toEqual(payload)
    expect(spy.mock.calls[0][0]).toBe('/documents/')
  })
})

describe('documentService.remove', () => {
  it('is named remove because delete is a reserved word', async () => {
    // The Phase 5 plan calls documentService.delete(...), which is not
    // expressible as a method name.
    expect('delete' in documentService).toBe(false)
    expect(typeof documentService.remove).toBe('function')
  })

  it('encodes the id in the path', async () => {
    const spy = vi.spyOn(apiClient, 'delete').mockResolvedValue({ data: undefined } as never)
    await documentService.remove('doc_a/b')

    expect(spy.mock.calls[0][0]).toBe('/documents/doc_a%2Fb')
  })
})

describe('documentService.stats', () => {
  it('returns the index statistics', async () => {
    const payload: IndexStats = {
      collection_name: 'course_documents',
      total_chunks: 4,
      embedding_provider: 'local',
      embedding_model: 'local-hash-2048',
      indexed_with: 'local-hash-2048',
    }
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: payload } as never)

    await expect(documentService.stats()).resolves.toEqual(payload)
    expect(spy.mock.calls[0][0]).toBe('/documents/stats')
  })
})
