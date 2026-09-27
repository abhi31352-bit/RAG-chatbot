import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SessionState {
  sessionId: string | null
  setSessionId: (id: string | null) => void
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      sessionId: null,
      setSessionId: (sessionId) => set({ sessionId }),
    }),
    {
      name: 'rag-chat-session',
    },
  ),
)

export function resetSessionStore(): void {
  useSessionStore.setState({ sessionId: null })
}
