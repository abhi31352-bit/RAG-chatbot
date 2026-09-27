import { useCallback, useEffect } from 'react'
import { documentService } from '../services/documentService'
import { useDocumentStore } from '../stores/documentStore'
import type { Document } from '../types'

/** Human-readable text for anything the services can reject with. */
function messageOf(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

/**
 * Document management for the admin panel.
 *
 * The hook owns the requests as well as the resulting state. Splitting them
 * -- the card sending the DELETE while the hook only dropped the row -- means
 * the hook's `remove` looks like it deletes but is really just a local splice,
 * so a failed delete silently removes the document from the list and it comes
 * back on the next refresh with no explanation.
 */
export const useDocuments = () => {
  const documents = useDocumentStore((state) => state.documents)
  const isLoading = useDocumentStore((state) => state.isLoading)
  const isUploading = useDocumentStore((state) => state.isUploading)
  const uploadProgress = useDocumentStore((state) => state.uploadProgress)
  const uploadPhase = useDocumentStore((state) => state.uploadPhase)
  const deletingId = useDocumentStore((state) => state.deletingId)
  const notice = useDocumentStore((state) => state.notice)
  const error = useDocumentStore((state) => state.error)

  const setDocuments = useDocumentStore((state) => state.setDocuments)
  const addDocument = useDocumentStore((state) => state.addDocument)
  const removeDocument = useDocumentStore((state) => state.removeDocument)
  const setLoading = useDocumentStore((state) => state.setLoading)
  const setUploadProgress = useDocumentStore((state) => state.setUploadProgress)
  const setUploadPhase = useDocumentStore((state) => state.setUploadPhase)
  const setUploading = useDocumentStore((state) => state.setUploading)
  const setDeletingId = useDocumentStore((state) => state.setDeletingId)
  const setNotice = useDocumentStore((state) => state.setNotice)
  const setError = useDocumentStore((state) => state.setError)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await documentService.list()
      setDocuments(data.documents)
    } catch (err) {
      setError(messageOf(err, 'Could not load documents. Is the backend running?'))
    } finally {
      setLoading(false)
    }
  }, [setDocuments, setError, setLoading])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const upload = useCallback(
    async (file: File): Promise<Document | null> => {
      setUploading(true)
      setUploadPhase('uploading')
      setUploadProgress(0)
      setError(null)
      setNotice(null)

      try {
        // The bytes have all been sent by the time progress hits 100%, but the
        // request is still open: the backend parses, chunks and embeds before
        // it responds. Relabel the bar so the wait is not mistaken for a
        // stall.
        const onProgress = (percent: number) => {
          setUploadProgress(percent)
          if (percent >= 100) setUploadPhase('indexing')
        }

        const doc = await documentService.upload(file, onProgress)
        addDocument(doc)
        setNotice(
          doc.chunk_count === 1
            ? `Indexed "${doc.filename}" as 1 chunk.`
            : `Indexed "${doc.filename}" as ${doc.chunk_count} chunks.`,
        )
        return doc
      } catch (err) {
        setError(messageOf(err, `Could not upload "${file.name}".`))
        return null
      } finally {
        setUploading(false)
        setUploadPhase('idle')
        setUploadProgress(0)
      }
    },
    [addDocument, setError, setNotice, setUploading, setUploadPhase, setUploadProgress],
  )

  const remove = useCallback(
    async (id: string): Promise<boolean> => {
      setDeletingId(id)
      setError(null)
      setNotice(null)

      try {
        await documentService.remove(id)
        // Only drop the row once the server has confirmed, so a rejected
        // delete leaves the list matching the server.
        removeDocument(id)
        setNotice('Document deleted, and its chunks removed from the index.')
        return true
      } catch (err) {
        setError(messageOf(err, 'Could not delete the document.'))
        return false
      } finally {
        setDeletingId(null)
      }
    },
    [removeDocument, setDeletingId, setError, setNotice],
  )

  return {
    documents,
    isLoading,
    isUploading,
    uploadProgress,
    uploadPhase,
    deletingId,
    notice,
    error,
    refresh,
    upload,
    remove,
  }
}
