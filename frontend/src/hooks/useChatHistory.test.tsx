import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useChatHistory } from './useChatHistory'
import { resetChatStore, useChatStore } from '../stores/chatStore'
import { resetSessionStore, useSessionStore } from '../stores/sessionStore'
import { chatService } from '../services/chatService'
import { ApiError } from '../services/apiClient'

vi.mock('../services/chatService', () => ({
  chatService: {
    streamQuery: vi.fn(),
    clearSession: vi.fn(),
    getHistory: vi.fn(),
  },
}))

const getHistory = vi.mocked(chatService.getHistory)

const storedMessage = {
  role: 'user',
  content: 'What counts for the grade?',
  sources: [],
  created_at: '2026-09-27T07:32:18.321039',
}

beforeEach(() => {
  resetChatStore()
  resetSessionStore()
  getHistory.mockReset()
})

describe('useChatHistory', () => {
  it('does nothing when there is no stored session', () => {
    getHistory.mockResolvedValue([])
    const { result } = renderHook(() => useChatHistory())

    expect(getHistory).not.toHaveBeenCalled()
    expect(result.current.isRestoring).toBe(false)
  })

  it('restores the messages for a persisted session', async () => {
    // The session id is persisted to localStorage but the messages are not.
    // Without this the page reloads to an empty chat while the server still
    // holds the history, and the next question is answered with context the
    // user cannot see.
    useSessionStore.getState().setSessionId('sess_abc')
    getHistory.mockResolvedValue([
      storedMessage,
      {
        role: 'assistant',
        content: 'The final exam is 40 percent.',
        sources: [
          {
            document_id: 'doc_1',
            filename: 'syllabus.txt',
            chunk_index: 0,
            excerpt: 'The final examination accounts for 40 percent.',
            similarity: 0.42,
          },
        ],
        created_at: '2026-09-27T07:32:19',
      },
    ])

    const { result } = renderHook(() => useChatHistory())

    expect(result.current.isRestoring).toBe(true)
    await waitFor(() => expect(result.current.isRestoring).toBe(false))

    const { messages } = useChatStore.getState()
    expect(messages).toHaveLength(2)
    expect(messages[0].role).toBe('user')
    expect(messages[0].content).toBe('What counts for the grade?')
    expect(messages[1].sources).toHaveLength(1)
  })

  it('converts created_at into a real Date', async () => {
    useSessionStore.getState().setSessionId('sess_abc')
    getHistory.mockResolvedValue([storedMessage])

    renderHook(() => useChatHistory())
    await waitFor(() => expect(useChatStore.getState().messages).toHaveLength(1))

    expect(useChatStore.getState().messages[0].timestamp).toBeInstanceOf(Date)
    expect(useChatStore.getState().messages[0].timestamp.getFullYear()).toBe(2026)
  })

  it('treats an empty history as a clean start', async () => {
    // The server answers 200 with an empty list for a session it has since
    // forgotten, e.g. after a restart.
    useSessionStore.getState().setSessionId('sess_abc')
    getHistory.mockResolvedValue([])

    renderHook(() => useChatHistory())
    await waitFor(() => expect(useChatStore.getState().messages).toEqual([]))

    expect(useSessionStore.getState().sessionId).toBe('sess_abc')
  })

  it('starts a new session when the stored one is gone', async () => {
    useSessionStore.getState().setSessionId('sess_abc')
    getHistory.mockRejectedValue(new ApiError('Not found', 'NOT_FOUND', 404))
    // The hook logs this deliberately; keep it out of the test output.
    vi.spyOn(console, 'warn').mockImplementation(() => {})

    renderHook(() => useChatHistory())
    await waitFor(() => expect(useSessionStore.getState().sessionId).toBeNull())

    expect(useChatStore.getState().messages).toEqual([])
  })

  it('does not overwrite a live conversation when a new session id arrives', async () => {
    // The first answer's terminal frame is what mints the session id. If that
    // triggered a hydrate, the server's snapshot at that instant would replace
    // the message currently on screen.
    getHistory.mockResolvedValue([])
    const { result } = renderHook(() => useChatHistory())

    await act(async () => {
      useSessionStore.getState().setSessionId('sess_new')
      await Promise.resolve()
    })

    expect(getHistory).not.toHaveBeenCalled()
    expect(result.current.isRestoring).toBe(false)
  })

  it('does not re-hydrate a session it has already restored', async () => {
    useSessionStore.getState().setSessionId('sess_abc')
    getHistory.mockResolvedValue([storedMessage])

    const { rerender } = renderHook(() => useChatHistory())
    await waitFor(() => expect(getHistory).toHaveBeenCalledTimes(1))

    rerender()
    await Promise.resolve()

    expect(getHistory).toHaveBeenCalledTimes(1)
  })

  it('ignores a response that arrives after unmount', async () => {
    useSessionStore.getState().setSessionId('sess_abc')
    let release: (messages: never[]) => void = () => {}
    getHistory.mockReturnValue(
      new Promise((resolve) => {
        release = resolve as (messages: never[]) => void
      }),
    )

    const { unmount } = renderHook(() => useChatHistory())
    unmount()
    release([storedMessage] as never[])
    await Promise.resolve()

    // Writing to a store a torn-down component subscribed to is a leak; the
    // cancelled flag is what prevents it.
    expect(useChatStore.getState().messages).toEqual([])
  })
})
