import { create } from 'zustand'
import type { Message, Source } from '../types'

export type { Message, Source } from '../types'

interface ChatState {
  messages: Message[]
  isLoading: boolean
  error: string | null
  isStreaming: boolean
  streamingContent: string
  streamingSources: Source[]
  /** 'openai' or 'offline-extractive' for the most recent answer. */
  mode: string | null

  addMessage: (message: Message) => void
  setMessages: (messages: Message[]) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setStreaming: (streaming: boolean) => void
  setStreamingContent: (content: string) => void
  setStreamingSources: (sources: Source[]) => void
  setMode: (mode: string | null) => void
  appendStreamingContent: (delta: string) => void
  clearMessages: () => void
  /** Promote whatever has streamed in so far into a real message. */
  finishStreaming: (sources?: Source[], mode?: string | null) => void
  /** Drop an in-progress answer without recording it. */
  discardStreaming: () => void
}

let idCounter = 0

/**
 * Ids must be unique within a render, and `Date.now()` is not: a user message
 * and the assistant reply that follows it can land in the same millisecond,
 * which React would treat as a duplicate key and silently reuse one bubble.
 */
export function newMessageId(): string {
  idCounter += 1
  return `msg_${Date.now()}_${idCounter}`
}

const initial = {
  messages: [] as Message[],
  isLoading: false,
  error: null as string | null,
  isStreaming: false,
  streamingContent: '',
  streamingSources: [] as Source[],
  mode: null as string | null,
}

export const useChatStore = create<ChatState>((set) => ({
  ...initial,

  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),

  setMessages: (messages) => set({ messages }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error }),

  setStreaming: (isStreaming) => set({ isStreaming }),

  setStreamingContent: (streamingContent) => set({ streamingContent }),

  setStreamingSources: (streamingSources) => set({ streamingSources }),

  setMode: (mode) => set({ mode }),

  appendStreamingContent: (delta) =>
    set((state) => ({ streamingContent: state.streamingContent + delta })),

  // Reset the streaming buffer too, or a half-written answer survives a clear.
  clearMessages: () => set({ ...initial }),

  finishStreaming: (sources, mode) =>
    set((state) => {
      const content = state.streamingContent
      const resolvedSources = sources ?? state.streamingSources
      // An empty answer is a failure that already surfaced as an error; adding
      // a blank bubble would only hide it.
      if (!content.trim() && resolvedSources.length === 0) {
        return { isStreaming: false, streamingContent: '', streamingSources: [] }
      }
      return {
        messages: [
          ...state.messages,
          {
            id: newMessageId(),
            role: 'assistant' as const,
            content,
            sources: resolvedSources,
            timestamp: new Date(),
            mode: mode ?? state.mode,
          },
        ],
        isLoading: false,
        error: null,
        isStreaming: false,
        streamingContent: '',
        streamingSources: [],
      }
    }),

  discardStreaming: () =>
    set({ isStreaming: false, streamingContent: '', streamingSources: [] }),
}))

/** Reset helper for tests. */
export function resetChatStore(): void {
  useChatStore.setState({ ...initial })
}
