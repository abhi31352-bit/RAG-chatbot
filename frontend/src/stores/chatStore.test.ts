import { beforeEach, describe, expect, it } from 'vitest'
import { newMessageId, resetChatStore, useChatStore } from './chatStore'
import type { Message, Source } from '../types'

const SOURCE: Source = {
  document_id: 'doc_1',
  filename: 'syllabus.txt',
  chunk_index: 0,
  excerpt: 'The final exam is worth 40 percent.',
  similarity: 0.42,
}

const userMessage = (content: string): Message => ({
  id: newMessageId(),
  role: 'user',
  content,
  sources: [],
  timestamp: new Date(),
})

beforeEach(() => {
  resetChatStore()
})

describe('newMessageId', () => {
  it('never repeats, even within the same millisecond', () => {
    // React keys off id, so two messages sharing one id means one bubble
    // silently renders twice or not at all.
    const ids = Array.from({ length: 1000 }, () => newMessageId())
    expect(new Set(ids).size).toBe(1000)
  })
})

describe('appendStreamingContent', () => {
  it('concatenates deltas in order', () => {
    useChatStore.getState().appendStreamingContent('Hello')
    useChatStore.getState().appendStreamingContent(', ')
    useChatStore.getState().appendStreamingContent('world')

    expect(useChatStore.getState().streamingContent).toBe('Hello, world')
  })
})

describe('finishStreaming', () => {
  it('promotes streamed text into an assistant message with its sources', () => {
    const store = useChatStore.getState()
    store.addMessage(userMessage('What counts for the grade?'))
    store.appendStreamingContent('The final exam is 40 percent.')
    store.setStreaming(true)

    useChatStore.getState().finishStreaming([SOURCE], 'offline-extractive')

    const { messages, isStreaming, streamingContent } = useChatStore.getState()
    expect(messages).toHaveLength(2)
    expect(messages[1].role).toBe('assistant')
    expect(messages[1].content).toBe('The final exam is 40 percent.')
    // Without this the citations from the terminal frame are thrown away.
    expect(messages[1].sources).toEqual([SOURCE])
    expect(messages[1].mode).toBe('offline-extractive')
    expect(isStreaming).toBe(false)
    expect(streamingContent).toBe('')
  })

  it('keeps the user message that came before it', () => {
    // Regression guard: spreading the reset defaults after `messages` wiped
    // the conversation entirely.
    const question = userMessage('Question?')
    useChatStore.getState().addMessage(question)
    useChatStore.getState().appendStreamingContent('Answer.')

    useChatStore.getState().finishStreaming()

    const { messages } = useChatStore.getState()
    expect(messages[0]).toBe(question)
    expect(messages[1].role).toBe('assistant')
  })

  it('adds no bubble when nothing arrived', () => {
    // An empty answer means the turn failed; the error banner is the story and
    // a blank bubble would only hide it.
    useChatStore.getState().setStreaming(true)
    useChatStore.getState().finishStreaming()

    expect(useChatStore.getState().messages).toHaveLength(0)
    expect(useChatStore.getState().isStreaming).toBe(false)
  })

  it('still records a message when there are sources but no text', () => {
    useChatStore.getState().setStreaming(true)
    useChatStore.getState().finishStreaming([SOURCE])

    const { messages } = useChatStore.getState()
    expect(messages).toHaveLength(1)
    expect(messages[0].sources).toEqual([SOURCE])
  })

  it('falls back to sources already held in the store', () => {
    useChatStore.getState().appendStreamingContent('Partial answer')
    useChatStore.getState().setStreamingSources([SOURCE])

    useChatStore.getState().finishStreaming()

    expect(useChatStore.getState().messages[0].sources).toEqual([SOURCE])
  })
})

describe('discardStreaming', () => {
  it('drops the buffer and leaves existing messages alone', () => {
    useChatStore.getState().addMessage(userMessage('Question?'))
    useChatStore.getState().appendStreamingContent('half an ans')
    useChatStore.getState().setStreaming(true)

    useChatStore.getState().discardStreaming()

    const { messages, isStreaming, streamingContent } = useChatStore.getState()
    expect(messages).toHaveLength(1)
    expect(isStreaming).toBe(false)
    expect(streamingContent).toBe('')
  })
})

describe('clearMessages', () => {
  it('resets the streaming buffer too', () => {
    useChatStore.getState().addMessage(userMessage('Question?'))
    useChatStore.getState().appendStreamingContent('half-written')
    useChatStore.getState().setStreaming(true)
    useChatStore.getState().setError('boom')
    useChatStore.getState().setMode('openai')

    useChatStore.getState().clearMessages()

    const state = useChatStore.getState()
    // Leaving the buffer behind shows stale text in the next conversation.
    expect(state.streamingContent).toBe('')
    expect(state.isStreaming).toBe(false)
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
    expect(state.mode).toBeNull()
    expect(state.messages).toEqual([])
  })
})

describe('setMessages', () => {
  it('replaces the conversation wholesale, as history restore does', () => {
    useChatStore.getState().setMessages([userMessage('restored')])

    expect(useChatStore.getState().messages).toHaveLength(1)
    expect(useChatStore.getState().messages[0].content).toBe('restored')
  })
})
