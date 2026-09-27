import { apiClient } from './apiClient'
import type { Document, DocumentListResponse, IndexStats } from '../types'

export type { Document, DocumentListResponse, IndexStats } from '../types'

export const documentService = {
  async upload(file: File, onProgress?: (progress: number) => void): Promise<Document> {
    const formData = new FormData()
    formData.append('file', file)

    // `apiClient` sets a default `Content-Type: application/json`, and axios
    // merges instance headers into every request, so that default reaches the
    // upload too. Left in place it is worse than useless: with a Content-Type
    // already present the browser will NOT generate a multipart boundary, and
    // the server receives a body it cannot parse. That failure is silent from
    // the client's point of view -- it arrives as a 422 reading
    // `{"loc":["body","file"],"msg":"Field required"}`, which looks like a
    // missing form field rather than a broken header.
    //
    // Setting the value to `undefined` is the documented way to delete an
    // inherited header in axios 1.x, which leaves the browser to pick
    // `multipart/form-data; boundary=...` itself. Naming
    // 'multipart/form-data' explicitly would be wrong: that gets sent
    // verbatim, without a boundary.
    const response = await apiClient.post<Document>('/documents/upload', formData, {
      timeout: 120000,
      headers: { 'Content-Type': undefined },
      onUploadProgress: (event) => {
        // `total` is 0 for chunked bodies, in which case the ratio is
        // meaningless -- report the single 100% completion instead of a
        // division by zero or a stuck bar.
        if (!onProgress) return
        if (event.total) {
          onProgress(Math.min(100, Math.round((event.loaded * 100) / event.total)))
        } else if (event.loaded > 0) {
          onProgress(100)
        }
      },
    })
    return response.data
  },

  async list(): Promise<DocumentListResponse> {
    // Trailing slash matters: the route is registered as `/documents/`, and
    // omitting it costs a 307 redirect on every list call.
    const response = await apiClient.get<DocumentListResponse>('/documents/')
    return response.data
  },

  async stats(): Promise<IndexStats> {
    const response = await apiClient.get<IndexStats>('/documents/stats')
    return response.data
  },

  async get(id: string): Promise<Document> {
    const response = await apiClient.get<Document>(`/documents/${encodeURIComponent(id)}`)
    return response.data
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/documents/${encodeURIComponent(id)}`)
  },
}
