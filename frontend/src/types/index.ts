/**
 * Shapes mirroring the backend contract in `architecture.md` section 5.
 *
 * Field names are snake_case on purpose: they are the keys the API actually
 * sends, and renaming them on the client would mean a translation layer that
 * can only ever be wrong in one direction.
 */

export interface Source {
  document_id: string
  filename: string
  chunk_index: number
  excerpt: string
  similarity: number
}

export type MessageRole = 'user' | 'assistant'

export interface Message {
  id: string
  role: MessageRole
  content: string
  sources: Source[]
  /** Set for messages restored from `GET /api/chat/history/{session_id}`. */
  timestamp: Date
  mode?: string | null
}

/** Wire format of a message coming back from the history endpoint. */
export interface HistoryMessage {
  role: string
  content: string
  sources: Source[]
  created_at: string | null
}

export interface ChatRequest {
  question: string
  session_id?: string
  include_sources?: boolean
}

export interface ChatResponse {
  answer: string
  sources: Source[]
  session_id: string
  processing_time_ms: number
  /**
   * Which generator produced the answer: 'groq', 'openai', or
   * 'offline-extractive'. A string rather than a union because the set of
   * remote providers is open; the UI must only special-case offline mode.
   */
  mode: string
  used_context: boolean
}

export interface Document {
  id: string
  filename: string
  /** Extension with no leading dot, e.g. 'pdf'. */
  file_type: string
  file_size: number
  chunk_count: number
  status: 'pending' | 'processed' | 'failed' | string
  created_at: string
}

export interface DocumentListResponse {
  documents: Document[]
  total: number
}

/**
 * Body of `GET /api/documents/stats`.
 *
 * `indexed_with` and `embedding_model` are the two halves of the embedding
 * compatibility check the backend enforces on upload: the first records what
 * the existing index was *built* with, the second what is active *now*. They
 * are usually identical, and the admin panel treats a difference as a problem
 * worth showing rather than something to hide.
 */
export interface IndexStats {
  collection_name: string
  total_chunks: number
  embedding_provider: string
  embedding_model: string
  indexed_with: string | null
}

/** Body of `GET /api/health`. */
export interface HealthStatus {
  status: string
  app_name: string
  environment: string
  llm_model: string
}

/** Body of `GET /api/health/ready`. */
export interface ReadinessStatus {
  ready: boolean
  checks: Record<string, boolean>
}

/** One decoded `data:` payload from the streaming endpoint. */
export interface StreamEvent {
  delta: string
  finish: boolean
  sources: Source[]
  session_id: string | null
  mode: string | null
  /** Set when the stream failed after the response headers were sent. */
  error: string | null
}
