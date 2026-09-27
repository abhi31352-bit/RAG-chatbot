import { API_BASE_URL, ApiError, apiClient } from './apiClient'
import { SSEParser } from './sse'
import type { ChatRequest, ChatResponse, HistoryMessage, StreamEvent } from '../types'

export type { ChatRequest, ChatResponse, HistoryMessage, Source, StreamEvent } from '../types'

export interface ClearSessionResponse {
  status: string
  session_id: string
  messages_removed: number
}

export const chatService = {
  async query(request: ChatRequest): Promise<ChatResponse> {
    const response = await apiClient.post<ChatResponse>('/chat/query', request)
    return response.data
  },

  /**
   * Stream an answer, yielding one event per `data:` frame.
   *
   * `fetch` rather than `EventSource`: the request is a POST with a JSON body,
   * and `EventSource` can only issue bodiless GETs. The cost is parsing SSE by
   * hand, which `SSEParser` handles.
   */
  async *streamQuery(
    request: ChatRequest,
    signal?: AbortSignal,
  ): AsyncGenerator<StreamEvent, void, unknown> {
    const response = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(request),
      signal,
    })

    if (!response.ok) {
      // Before the stream starts, the backend answers with the normal JSON
      // error envelope rather than an event stream.
      throw await toStreamError(response)
    }

    const body = response.body
    if (!body) {
      throw new ApiError('The server sent an empty response', 'EMPTY_BODY', response.status)
    }

    const reader = body.getReader()
    const decoder = new TextDecoder()
    const parser = new SSEParser()

    try {
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break

        // `{stream: true}` holds back a multi-byte character split across two
        // network chunks; without it a split emoji becomes a replacement
        // character mid-sentence.
        for (const event of parser.push(decoder.decode(value, { stream: true }))) {
          yield event
        }
      }

      // Flush both the decoder (final bytes held back) and the parser (a frame
      // the server never terminated with a newline).
      for (const event of parser.push(decoder.decode())) {
        yield event
      }
      for (const event of parser.flush()) {
        yield event
      }

      if (parser.malformedCount > 0) {
        console.warn(`Dropped ${parser.malformedCount} unparseable stream frame(s)`)
      }
    } finally {
      // Releasing the lock lets an aborted request tear the connection down
      // instead of leaving the body open.
      reader.releaseLock()
    }
  },

  async getHistory(sessionId: string): Promise<HistoryMessage[]> {
    const response = await apiClient.get<{ session_id: string; messages: HistoryMessage[] }>(
      `/chat/history/${encodeURIComponent(sessionId)}`,
    )
    return response.data.messages ?? []
  },

  async clearSession(sessionId: string): Promise<ClearSessionResponse> {
    const response = await apiClient.post<ClearSessionResponse>('/chat/clear', {
      session_id: sessionId,
    })
    return response.data
  },
}

/** Turn a non-2xx stream response into the same error type axios produces. */
async function toStreamError(response: Response): Promise<ApiError> {
  let code = 'STREAM_FAILED'
  let message = `Stream request failed: ${response.status} ${response.statusText}`.trim()
  let details: unknown

  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string; details?: unknown } }
    if (body?.error) {
      code = body.error.code ?? code
      message = body.error.message ?? message
      details = body.error.details
    }
  } catch {
    // A non-JSON body (a proxy error page, say) leaves the status line as the
    // only thing worth reporting.
  }

  return new ApiError(message, code, response.status, details)
}
