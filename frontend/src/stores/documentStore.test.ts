import { describe, expect, it, beforeEach } from 'vitest'
import { useDocumentStore, resetDocumentStore } from './documentStore'
import type { Document } from '../types'

function doc(id: string, filename: string): Document {
  return {
    id,
    filename,
    file_type: 'txt',
    file_size: 10,
    chunk_count: 1,
    status: 'processed',
    created_at: '2026-03-04T10:00:00Z',
  }
}

beforeEach(() => {
  resetDocumentStore()
})

describe('documentStore', () => {
  it('starts empty and idle', () => {
    const state = useDocumentStore.getState()
    expect(state.documents).toEqual([])
    expect(state.uploadPhase).toBe('idle')
    expect(state.error).toBeNull()
  })

  it('prepends a new document so newest comes first', () => {
    // The backend lists newest first (created_at desc), so prepending matches
    // what a refresh would return instead of reordering on the next load.
    useDocumentStore.getState().setDocuments([doc('a', 'a.txt')])
    useDocumentStore.getState().addDocument(doc('b', 'b.txt'))

    expect(useDocumentStore.getState().documents.map((d) => d.id)).toEqual(['b', 'a'])
  })

  it('removes only the requested document', () => {
    useDocumentStore.getState().setDocuments([doc('a', 'a.txt'), doc('b', 'b.txt')])
    useDocumentStore.getState().removeDocument('a')

    expect(useDocumentStore.getState().documents.map((d) => d.id)).toEqual(['b'])
  })

  it('tracks which document is being deleted', () => {
    useDocumentStore.getState().setDeletingId('doc_1')
    expect(useDocumentStore.getState().deletingId).toBe('doc_1')
  })

  it('fully resets every field', () => {
    useDocumentStore.setState({
      documents: [doc('a', 'a.txt')],
      isLoading: true,
      isUploading: true,
      uploadProgress: 42,
      uploadPhase: 'indexing',
      deletingId: 'a',
      notice: 'done',
      error: 'bad',
    })

    resetDocumentStore()

    expect(useDocumentStore.getState()).toMatchObject({
      documents: [],
      isLoading: false,
      isUploading: false,
      uploadProgress: 0,
      uploadPhase: 'idle',
      deletingId: null,
      notice: null,
      error: null,
    })
  })
})
