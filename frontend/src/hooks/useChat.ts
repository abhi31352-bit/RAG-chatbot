import { useCallback, useEffect, useRef } from 'react'
import { newMessageId, useChatStore } from '../stores/chatStore'
import { useSessionStore } from '../stores/sessionStore'
import { chatService } from '../services/chatService'
import { ApiError } from '../services/apiClient'
import type { Message, Source } from '../types'

export function useChat() {
  const messages = useChatStore((s) => s.messages)
  const isLoading = useChatStore((s) => s.isLoading)
  const error = useChatStore((s) => s.error)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const streamingContent = useChatStore((s) => s.streamingContent)
  const mode = useChatStore((s) => s.mode)

  const addMessage = useChatStore((s) => s.addMessage)
  const setLoading = useChatStore((s) => s.setLoading)
  const setError = useChatStore((s) => s.setError)
  const setMode = useChatStore((s) => s.setMode)
  const setStreaming = useChatStore((s) => s.setStreaming)
  const setStreamingContent = useChatStore((s) => s.setStreamingContent)
  const setStreamingSources = useChatStore((s) => s.setStreamingSources)
  const appendStreamingContent = useChatStore((s) => s.appendStreamingContent)
  const finishStreaming = useChatStore((s) => s.finishStreaming)
  const discardStreaming = useChatStore((s) => s.discardStreaming)
  const clearMessages = useChatStore((s) => s.clearMessages)

  const sessionId = useSessionStore((s) => s.sessionId)
  const setSessionId = useSessionStore((s) => s.setSessionId)

  const abortRef = useRef<AbortController | null>(null)

  // An in-flight request must not keep writing into the store after the
  // component that owns it has gone away.
  useEffect(() => () => abortRef.current?.abort(), [])

  const sendMessage = useCallback(
    async (question: string) => {
      const trimmed = question.trim()
      if (!trimmed || isLoading || isStreaming) return

      addMessage({
        id: newMessageId(),
        role: 'user',
        content: trimmed,
        sources: [],
        timestamp: new Date(),
      })

      setLoading(true)
      setError(null)
      setMode(null)
      setStreamingContent('')
      setStreamingSources([])
      setStreaming(true)

      const controller = new AbortController()
      abortRef.current = controller
      let finalized = false

      try {
        for await (const event of chatService.streamQuery(
          { question: trimmed, session_id: sessionId ?? undefined },
          controller.signal,
        )) {
          // The session id is minted server-side and only ever appears on the
          // terminal frame. Ignoring it means every turn starts a brand new
          // session and the assistant has no memory of the conversation.
          if (event.session_id) {
            setSessionId(event.session_id)
          }
          if (event.mode) {
            setMode(event.mode)
          }
          // Once the headers are sent the status code is fixed, so failures
          // mid-stream arrive as a terminal frame carrying `error`.
          if (event.error) {
            // The server ended the stream deliberately. Keep whatever arrived
            // and record that it ended here, rather than letting the
            // dropped-connection path below overwrite the real reason.
            const { streamingContent: partial, streamingSources: partialSources } =
              useChatStore.getState()
            if (partial.trim() || partialSources.length > 0) {
              finishStreaming(event.sources.length ? event.sources : partialSources, event.mode)
            } else {
              discardStreaming()
            }
            // finishStreaming clears the error field, so set it afterwards.
            setError(event.error)
            finalized = true
            break
          }
          if (event.finish) {
            finishStreaming(event.sources, event.mode)
            finalized = true
          } else if (event.delta) {
            appendStreamingContent(event.delta)
          }
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(describeError(err))
        }
      } finally {
        // If the connection dropped before the finish frame, reconcile by hand.
        // Without this, `isStreaming` stays true forever and the input box is
        // disabled for the rest of the session.
        if (!finalized && !controller.signal.aborted) {
          const { streamingContent: partial, streamingSources: partialSources } =
            useChatStore.getState()
          if (partial.trim() || partialSources.length > 0) {
            finishStreaming(partialSources)
            setError('The connection dropped before the answer finished. Showing what arrived.')
          } else {
            discardStreaming()
          }
        }
        setLoading(false)
        abortRef.current = null
      }
    },
    [
      isLoading,
      isStreaming,
      sessionId,
      addMessage,
      setLoading,
      setError,
      setMode,
      setStreaming,
      setStreamingContent,
      setStreamingSources,
      appendStreamingContent,
      finishStreaming,
      discardStreaming,
      setSessionId,
    ],
  )

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    const { streamingContent, streamingSources } = useChatStore.getState()
    if (streamingContent.trim() || streamingSources.length > 0) {
      // Keep what arrived: a stopped stream usually has a usable partial
      // answer, and silently dropping it looks like the app hung.
      finishStreaming(streamingSources)
    } else {
      discardStreaming()
    }
    setLoading(false)
  }, [finishStreaming, discardStreaming, setLoading])

  const clearChat = useCallback(async () => {
    abortRef.current?.abort()
    abortRef.current = null
    setLoading(false)
    discardStreaming()
    clearMessages()
    if (sessionId) {
      // Best effort: the local conversation is already gone either way, and a
      // failure here should not leave the button looking broken.
      try {
        await chatService.clearSession(sessionId)
      } catch (err) {
        console.warn('Failed to clear the session on the server:', err)
      }
    }
    setSessionId(null)
  }, [sessionId, clearMessages, discardStreaming, setLoading, setSessionId])

  return {
    messages,
    isLoading,
    error,
    isStreaming,
    streamingContent,
    mode,
    sendMessage,
    stopStreaming,
    clearChat,
  }
}

function describeError(err: unknown): string {
  if (err instanceof ApiError) return err.message
  if (err instanceof Error) return err.message
  return 'Failed to get a response'
}

/** Convert a stored history message into a renderable client message. */
export function toMessage(raw: {
  role: string
  content: string
  sources?: Source[]
  created_at?: string | null
}): Message {
  return {
    id: newMessageId(),
    role: raw.role === 'user' ? 'user' : 'assistant',
    content: raw.content,
    sources: raw.sources ?? [],
    timestamp: raw.created_at ? new Date(raw.created_at) : new Date(),
  }
}
