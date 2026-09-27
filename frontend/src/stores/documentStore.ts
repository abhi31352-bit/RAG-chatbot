import { create } from 'zustand'
import type { Document } from '../types'

export type { Document } from '../types'

/**
 * Where an upload currently is.
 *
 * The distinction matters because the backend parses, chunks and embeds the
 * file *inside* the upload request, so the bytes finish travelling long before
 * the response arrives. Collapsing this to a single boolean would leave the
 * progress bar sitting at 100% and frozen for the entire indexing step, which
 * reads as a hang.
 */
export type UploadPhase = 'idle' | 'uploading' | 'indexing'

interface DocumentState {
  documents: Document[]
  isLoading: boolean
  isUploading: boolean
  uploadProgress: number
  uploadPhase: UploadPhase
  /** Id of the document currently being deleted, for a per-row spinner. */
  deletingId: string | null
  /** Set after a successful upload or delete; cleared on the next action. */
  notice: string | null
  error: string | null

  setDocuments: (documents: Document[]) => void
  addDocument: (document: Document) => void
  removeDocument: (id: string) => void
  setLoading: (isLoading: boolean) => void
  setUploading: (isUploading: boolean) => void
  setUploadProgress: (uploadProgress: number) => void
  setUploadPhase: (uploadPhase: UploadPhase) => void
  setDeletingId: (deletingId: string | null) => void
  setNotice: (notice: string | null) => void
  setError: (error: string | null) => void
}

export const useDocumentStore = create<DocumentState>((set) => ({
  documents: [],
  isLoading: false,
  isUploading: false,
  uploadProgress: 0,
  uploadPhase: 'idle',
  deletingId: null,
  notice: null,
  error: null,

  setDocuments: (documents) => set({ documents }),
  addDocument: (document) => set((state) => ({ documents: [document, ...state.documents] })),
  removeDocument: (id) =>
    set((state) => ({ documents: state.documents.filter((d) => d.id !== id) })),
  setLoading: (isLoading) => set({ isLoading }),
  setUploading: (isUploading) => set({ isUploading }),
  setUploadProgress: (uploadProgress) => set({ uploadProgress }),
  setUploadPhase: (uploadPhase) => set({ uploadPhase }),
  setDeletingId: (deletingId) => set({ deletingId }),
  setNotice: (notice) => set({ notice }),
  setError: (error) => set({ error }),
}))

export function resetDocumentStore(): void {
  useDocumentStore.setState({
    documents: [],
    isLoading: false,
    isUploading: false,
    uploadProgress: 0,
    uploadPhase: 'idle',
    deletingId: null,
    notice: null,
    error: null,
  })
}
