import { useEffect, useRef, useState } from 'react'
import { useChatStore } from '../stores/chatStore'
import { useSessionStore } from '../stores/sessionStore'
import { chatService } from '../services/chatService'
import { toMessage } from './useChat'

/**
 * Restore the visible conversation when the page reloads.
 *
 * The session id is persisted to localStorage but the messages are not, so on
 * a reload the client would otherwise show an empty chat while the server
 * still holds the history -- and the next question would be answered with
 * context the user cannot see. `GET /api/chat/history/{session_id}` exists for
 * exactly this.
 *
 * Hydration happens at most once, for the session that was already in
 * localStorage when the page loaded. It deliberately does not re-run for ids
 * that arrive during a conversation: the first answer's terminal frame is what
 * mints a session, and re-hydrating then would replace the message on screen
 * with the server's snapshot of that moment.
 */
export function useChatHistory(): { isRestoring: boolean } {
  const sessionId = useSessionStore((s) => s.sessionId)
  const setSessionId = useSessionStore((s) => s.setSessionId)
  const setMessages = useChatStore((s) => s.setMessages)
  const clearMessages = useChatStore((s) => s.clearMessages)
  const [isRestoring, setIsRestoring] = useState(false)

  // `useRef` keeps its first value for the lifetime of the component.
  const restoreFor = useRef<string | null>(useSessionStore.getState().sessionId)

  useEffect(() => {
    if (!sessionId || sessionId !== restoreFor.current) return

    let cancelled = false
    setIsRestoring(true)

    chatService
      .getHistory(sessionId)
      .then((messages) => {
        if (cancelled) return
        // An empty history is normal after a server restart wiped the session;
        // either way there is nothing to show, so start clean.
        setMessages(messages.map(toMessage))
      })
      .catch((err) => {
        if (cancelled) return
        console.warn('Could not restore the conversation, starting a new one:', err)
        setSessionId(null)
        clearMessages()
      })
      .finally(() => {
        if (!cancelled) setIsRestoring(false)
      })

    return () => {
      cancelled = true
    }
  }, [sessionId, setSessionId, setMessages, clearMessages])

  return { isRestoring }
}
