import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChatPage } from './ChatPage'
import { resetChatStore } from '../stores/chatStore'
import { resetSessionStore, useSessionStore } from '../stores/sessionStore'
import { chatService } from '../services/chatService'
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
const getHistory = vi.mocked(chatService.getHistory)

const SOURCE: Source = {
  document_id: 'doc_1',
  filename: 'syllabus.txt',
  chunk_index: 0,
  excerpt: 'The final examination accounts for 40 percent.',
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

beforeEach(() => {
  resetChatStore()
  resetSessionStore()
  localStorage.clear()
  streamQuery.mockReset()
  clearSession.mockReset().mockResolvedValue({
    status: 'cleared',
    session_id: 'sess_1',
    messages_removed: 0,
  })
  getHistory.mockReset().mockResolvedValue([])
})

describe('ChatPage', () => {
  it('asks a question and shows the streamed answer with its sources', async () => {
    const user = userEvent.setup()
    streamQuery.mockReturnValue(
      streamOf(
        event({ delta: 'The final examination accounts for ' }),
        event({ delta: '40 percent' }),
        event({ finish: true, sources: [SOURCE], session_id: 'sess_1', mode: 'offline-extractive' }),
      ),
    )

    render(<ChatPage />)
    await user.type(screen.getByLabelText('Your question'), 'What counts for the grade?')
    await user.click(screen.getByLabelText('Send'))

    // Match on the whole answer: the source excerpt repeats "40 percent", so a
    // substring match would be ambiguous.
    expect(
      await screen.findByText('The final examination accounts for 40 percent'),
    ).toBeInTheDocument()
    const card = await screen.findByTestId('source-card')
    expect(card).toHaveTextContent('syllabus.txt')
  })

  it('promotes the streamed text into a persistent message', async () => {
    const user = userEvent.setup()
    streamQuery.mockReturnValue(
      streamOf(event({ delta: 'An answer.' }), event({ finish: true })),
    )

    render(<ChatPage />)
    await user.type(screen.getByLabelText('Your question'), 'Question?')
    await user.click(screen.getByLabelText('Send'))

    await waitFor(() => expect(screen.queryByTestId('streaming-bubble')).not.toBeInTheDocument())
    expect(screen.getByText('An answer.')).toBeInTheDocument()
    // Both the question and the answer remain on screen.
    expect(screen.getByText('Question?')).toBeInTheDocument()
  })

  it('sends a suggested question when one is clicked', async () => {
    const user = userEvent.setup()
    streamQuery.mockReturnValue(
      streamOf(event({ delta: 'Answer.' }), event({ finish: true })),
    )

    render(<ChatPage />)
    await user.click(screen.getByRole('button', { name: /When are the office hours/i }))

    await waitFor(() => expect(streamQuery).toHaveBeenCalled())
    expect(streamQuery.mock.calls[0][0].question).toMatch(/office hours/i)
  })

  it('disables input during a turn and re-enables it after', async () => {
    const user = userEvent.setup()
    // Parks on the abort signal, so the stream is genuinely still in flight
    // when the stop button is pressed.
    streamQuery.mockImplementation((_request, signal) =>
      (async function* () {
        yield event({ delta: 'Thinking' })
        await new Promise<void>((resolve) => {
          if (signal?.aborted) resolve()
          else signal?.addEventListener('abort', () => resolve())
        })
        yield event({ finish: true })
      })(),
    )

    render(<ChatPage />)
    await user.type(screen.getByLabelText('Your question'), 'Question?')
    await user.click(screen.getByLabelText('Send'))

    await waitFor(() => expect(screen.getByLabelText('Stop generating')).toBeInTheDocument())
    await user.click(screen.getByLabelText('Stop generating'))

    await waitFor(() => expect(screen.getByLabelText('Send')).toBeInTheDocument())
    expect(screen.getByLabelText('Your question')).not.toBeDisabled()
  })

  it('reports a stream failure instead of rendering nothing', async () => {
    const user = userEvent.setup()
    streamQuery.mockReturnValue(
      streamOf(event({ finish: true, error: 'The language model is unavailable' })),
    )

    render(<ChatPage />)
    await user.type(screen.getByLabelText('Your question'), 'Question?')
    await user.click(screen.getByLabelText('Send'))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The language model is unavailable',
    )
  })

  it('reports an unanswered question when the server is unreachable', async () => {
    const user = userEvent.setup()
    streamQuery.mockImplementation(() => {
      throw new Error('Network Error')
    })

    render(<ChatPage />)
    await user.type(screen.getByLabelText('Your question'), 'Question?')
    await user.click(screen.getByLabelText('Send'))

    expect(await screen.findByRole('alert')).toHaveTextContent('Network Error')
  })

  it('shows a 429 rate-limit message', async () => {
    const user = userEvent.setup()
    const { ApiError } = await import('../services/apiClient')
    streamQuery.mockImplementation(() => {
      throw new ApiError('Too many requests. Try again in a minute.', 'RATE_LIMITED', 429)
    })

    render(<ChatPage />)
    await user.type(screen.getByLabelText('Your question'), 'Question?')
    await user.click(screen.getByLabelText('Send'))

    expect(await screen.findByRole('alert')).toHaveTextContent('Too many requests')
  })

  it('labels the generator so an offline answer is not mistaken for an LLM answer', async () => {
    const user = userEvent.setup()
    streamQuery.mockReturnValue(
      streamOf(
        event({ delta: 'Quoted sentence.' }),
        event({ finish: true, mode: 'offline-extractive' }),
      ),
    )

    render(<ChatPage />)
    await user.type(screen.getByLabelText('Your question'), 'Question?')
    await user.click(screen.getByLabelText('Send'))

    const badge = await screen.findByTestId('mode-badge')
    expect(badge).toHaveTextContent('Offline extractive')
    // The tooltip has to say plainly that no model was called.
    expect(badge).toHaveAttribute('title', expect.stringContaining('No language model was called'))
  })

  it('shows a different badge when a real model answered', async () => {
    const user = userEvent.setup()
    streamQuery.mockReturnValue(
      streamOf(event({ delta: 'A generated answer.' }), event({ finish: true, mode: 'openai' })),
    )

    render(<ChatPage />)
    await user.type(screen.getByLabelText('Your question'), 'Question?')
    await user.click(screen.getByLabelText('Send'))

    expect(await screen.findByTestId('mode-badge')).toHaveTextContent('Generated')
  })

  it('clears the conversation and the stored session', async () => {
    const user = userEvent.setup()
    streamQuery.mockReturnValue(
      streamOf(event({ delta: 'An answer.' }), event({ finish: true, session_id: 'sess_1' })),
    )

    render(<ChatPage />)
    await user.type(screen.getByLabelText('Your question'), 'Question?')
    await user.click(screen.getByLabelText('Send'))
    await screen.findByText('An answer.')

    await user.click(screen.getByRole('button', { name: /Clear chat/i }))

    await waitFor(() => expect(screen.queryByText('An answer.')).not.toBeInTheDocument())
    expect(clearSession).toHaveBeenCalledWith('sess_1')
    expect(useSessionStore.getState().sessionId).toBeNull()
  })

  it('restores a previous conversation on load', async () => {
    useSessionStore.getState().setSessionId('sess_previous')
    getHistory.mockResolvedValue([
      {
        role: 'user',
        content: 'Earlier question',
        sources: [],
        created_at: '2026-09-27T07:32:18',
      },
      {
        role: 'assistant',
        content: 'Earlier answer',
        sources: [SOURCE],
        created_at: '2026-09-27T07:32:19',
      },
    ])

    render(<ChatPage />)

    expect(await screen.findByText('Earlier answer')).toBeInTheDocument()
    expect(screen.getByText('Earlier question')).toBeInTheDocument()
    expect(screen.getByTestId('source-card')).toHaveTextContent('syllabus.txt')
  })

  it('hides suggested questions once there is a conversation', async () => {
    const user = userEvent.setup()
    streamQuery.mockReturnValue(
      streamOf(event({ delta: 'An answer.' }), event({ finish: true })),
    )

    render(<ChatPage />)
    expect(screen.getByRole('button', { name: /Who is the TA/i })).toBeInTheDocument()

    await user.type(screen.getByLabelText('Your question'), 'Question?')
    await user.click(screen.getByLabelText('Send'))
    await screen.findByText('An answer.')

    expect(screen.queryByRole('button', { name: /Who is the TA/i })).not.toBeInTheDocument()
  })
})
