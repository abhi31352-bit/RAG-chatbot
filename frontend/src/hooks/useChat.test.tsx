import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useChat } from './useChat'
import { resetChatStore } from '../stores/chatStore'
import { resetSessionStore, useSessionStore } from '../stores/sessionStore'
import { chatService } from '../services/chatService'
import { ApiError } from '../services/apiClient'
import type { Source, StreamEvent } from '../types'

vi.mock('../services/chatService', () => ({
  chatService: {
    streamQuery: vi.fn(),
    clearSession: vi.fn(),
    getHistory: vi.fn(),
  },
}))

const streamQuery = vi.mocked(chatService.streamQuery)
const clearSession = vi.mocked(chatService.clearSession)

const SOURCE: Source = {
  document_id: 'doc_1',
  filename: 'syllabus.txt',
  chunk_index: 0,
  excerpt: 'The final exam is worth 40 percent.',
  similarity: 0.42,
}

function event(partial: Partial<StreamEvent>): StreamEvent {
  return {
    delta: '',
    finish: false,
    sources: [],
    session_id: null,
    mode: null,
    error: null,
    ...partial,
  }
}

function streamOf(...events: StreamEvent[]): AsyncGenerator<StreamEvent, void, unknown> {
  return (async function* () {
    for (const e of events) yield e
  })()
}

/** A stream that emits `events` and then dies, mid-answer, with no finish frame. */
function streamThatDrops(...events: StreamEvent[]): AsyncGenerator<StreamEvent, void, unknown> {
  return (async function* () {
    for (const e of events) yield e
    throw new TypeError('network error')
  })()
}

/** A generator that ends cleanly but never sent a finish frame. */
function streamThatEndsEarly(...events: StreamEvent[]): AsyncGenerator<StreamEvent, void, unknown> {
  return (async function* () {
    for (const e of events) yield e
  })()
}

beforeEach(() => {
  resetChatStore()
  resetSessionStore()
  streamQuery.mockReset()
  clearSession.mockReset().mockResolvedValue({
    status: 'cleared',
    session_id: 'sess_1',
    messages_removed: 2,
  })
  localStorage.clear()
})

describe('sendMessage', () => {
  it('captures the session id from the terminal frame', async () => {
    // The session id is minted server-side and only appears on the finish
    // frame. Discarding it starts a brand new session every turn, so the
    // assistant never sees the earlier conversation.
    streamQuery.mockReturnValue(
      streamOf(
        event({ delta: 'The final exam is 40 percent.' }),
        event({ finish: true, session_id: 'sess_abc', mode: 'offline-extractive' }),
      ),
    )

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('What counts for the grade?')
    })

    expect(useSessionStore.getState().sessionId).toBe('sess_abc')
  })

  it('sends the captured session id on the next turn', async () => {
    streamQuery.mockReturnValue(
      streamOf(event({ finish: true, session_id: 'sess_abc' })),
    )

    const { result, rerender } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('First question')
    })

    // Re-render so the hook picks up the new session id from the store.
    rerender()
    streamQuery.mockReturnValue(
      streamOf(
        event({ delta: 'And Tuesday.' }),
        event({ finish: true, session_id: 'sess_abc' }),
      ),
    )
    await act(async () => {
      await result.current.sendMessage('Follow up question')
    })

    expect(streamQuery.mock.calls[1][0].session_id).toBe('sess_abc')
  })

  it('records the user message and the streamed answer', async () => {
    streamQuery.mockReturnValue(
      streamOf(
        event({ delta: 'Office hours are ' }),
        event({ delta: 'Tuesdays.' }),
        event({ finish: true, sources: [SOURCE] }),
      ),
    )

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('When are office hours?')
    })

    const { messages } = result.current
    expect(messages).toHaveLength(2)
    expect(messages[0]).toMatchObject({ role: 'user', content: 'When are office hours?' })
    expect(messages[1]).toMatchObject({
      role: 'assistant',
      content: 'Office hours are Tuesdays.',
    })
    expect(messages[1].sources).toEqual([SOURCE])
  })

  it('clears the loading and streaming flags when done', async () => {
    streamQuery.mockReturnValue(
      streamOf(event({ delta: 'Answer.' }), event({ finish: true })),
    )

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('Question?')
    })

    expect(result.current.isLoading).toBe(false)
    expect(result.current.isStreaming).toBe(false)
    expect(result.current.streamingContent).toBe('')
  })

  it('trims the question and ignores a blank one', async () => {
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('   \n  ')
    })
    expect(streamQuery).not.toHaveBeenCalled()

    streamQuery.mockReturnValue(streamOf(event({ finish: true })))
    await act(async () => {
      await result.current.sendMessage('  padded question  ')
    })
    expect(streamQuery.mock.calls[0][0].question).toBe('padded question')
  })
})

describe('stream failures', () => {
  it('shows a mid-stream error frame instead of an empty answer', async () => {
    // Once headers are sent the status code is fixed, so the backend reports
    // failures as a terminal frame carrying `error`.
    streamQuery.mockReturnValue(
      streamOf(
        event({ delta: 'Partial text' }),
        event({ finish: true, error: 'The language model is unavailable' }),
      ),
    )

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('Question?')
    })

    expect(result.current.error).toBe('The language model is unavailable')
    expect(result.current.isLoading).toBe(false)
    expect(result.current.isStreaming).toBe(false)
  })

  it('unblocks the input when the stream dies with nothing received', async () => {
    // Without reconciliation `isStreaming` stays true and the input box is
    // disabled for the rest of the session.
    streamQuery.mockReturnValue(streamThatDrops())

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('Question?')
    })

    expect(result.current.isLoading).toBe(false)
    expect(result.current.isStreaming).toBe(false)
    expect(result.current.error).toBeTruthy()
  })

  it('keeps a partial answer when the stream dies mid-way', async () => {
    streamQuery.mockReturnValue(streamThatDrops(event({ delta: 'Half an answer' })))

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('Question?')
    })

    expect(result.current.messages[1].content).toBe('Half an answer')
    expect(result.current.error).toContain('connection dropped')
  })

  it('finalises a stream that ended without a finish frame', async () => {
    // The connection closed cleanly but the terminal frame never arrived.
    streamQuery.mockReturnValue(streamThatEndsEarly(event({ delta: 'Almost done' })))

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('Question?')
    })

    expect(result.current.isStreaming).toBe(false)
    expect(result.current.messages[1].content).toBe('Almost done')
  })

  it('surfaces an API error message', async () => {
    streamQuery.mockImplementation(() => {
      throw new ApiError('RATE_LIMITED', 'RATE_LIMITED', 429)
    })

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('Question?')
    })

    expect(result.current.error).toBe('RATE_LIMITED')
    expect(result.current.isLoading).toBe(false)
  })
})

describe('stopStreaming', () => {
  it('keeps what already arrived and stops loading', async () => {
    // The generator parks until the abort signal fires, so the hook is
    // genuinely mid-stream when stopStreaming runs.
    streamQuery.mockImplementation((_request, signal) =>
      (async function* () {
        yield event({ delta: 'Started' })
        await new Promise<void>((resolve) => {
          if (signal?.aborted) resolve()
          else signal?.addEventListener('abort', () => resolve())
        })
      })(),
    )

    const { result } = renderHook(() => useChat())
    let send: Promise<void>
    await act(async () => {
      send = result.current.sendMessage('Question?')
      await Promise.resolve()
    })

    await waitFor(() => expect(result.current.streamingContent).toBe('Started'))
    await act(async () => {
      result.current.stopStreaming()
      await send
    })

    // A stopped stream usually has a usable partial answer; dropping it looks
    // like the app hung.
    expect(result.current.messages[1].content).toBe('Started')
    expect(result.current.isLoading).toBe(false)
    expect(result.current.isStreaming).toBe(false)
  })

  it('reports no error for a deliberately stopped stream', async () => {
    // The user chose to stop; a "connection dropped" warning would be a lie.
    streamQuery.mockImplementation((_request, signal) =>
      (async function* () {
        yield event({ delta: 'Partial' })
        await new Promise<void>((resolve) => {
          if (signal?.aborted) resolve()
          else signal?.addEventListener('abort', () => resolve())
        })
      })(),
    )

    const { result } = renderHook(() => useChat())
    let send: Promise<void>
    await act(async () => {
      send = result.current.sendMessage('Question?')
      // Flush the first delta so the effect settles before the assertions.
      await Promise.resolve()
    })
    await waitFor(() => expect(result.current.streamingContent).toBe('Partial'))
    await act(async () => {
      result.current.stopStreaming()
      await send
    })

    expect(result.current.error).toBeNull()
    expect(result.current.messages[1].content).toBe('Partial')
  })
})

describe('clearChat', () => {
  it('clears the server session, local messages and the stored id', async () => {
    useSessionStore.getState().setSessionId('sess_abc')
    streamQuery.mockReturnValue(
      streamOf(event({ delta: 'Answer.' }), event({ finish: true })),
    )

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('Question?')
    })
    await act(async () => {
      await result.current.clearChat()
    })

    expect(clearSession).toHaveBeenCalledWith('sess_abc')
    expect(result.current.messages).toEqual([])
    expect(useSessionStore.getState().sessionId).toBeNull()
  })

  it('still clears locally when the server call fails', async () => {
    // The conversation is gone either way; leaving the button stuck on an error
    // would be worse than a stale session on the server.
    useSessionStore.getState().setSessionId('sess_abc')
    clearSession.mockRejectedValue(new ApiError('boom', 'X', 500))
    vi.spyOn(console, 'warn').mockImplementation(() => {})

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.clearChat()
    })

    expect(useSessionStore.getState().sessionId).toBeNull()
    expect(result.current.messages).toEqual([])
  })

  it('does not call the server when there is no session', async () => {
    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.clearChat()
    })

    expect(clearSession).not.toHaveBeenCalled()
  })
})
