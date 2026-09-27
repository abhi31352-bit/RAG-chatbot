import React from 'react'
import { AlertCircle, MessageSquare, Trash2 } from 'lucide-react'
import { InputBox } from '../components/Chat/InputBox'
import { MessageList } from '../components/Chat/MessageList'
import { ModeBadge } from '../components/Chat/ModeBadge'
import { SuggestedQuestions } from '../components/Chat/SuggestedQuestions'
import { useChat } from '../hooks/useChat'
import { useChatHistory } from '../hooks/useChatHistory'

/**
 * Offered when the chat is empty.
 *
 * Every one of these was checked to return a grounded answer rather than the
 * "I don't have information" fallback. In offline mode the generator matches
 * question terms against sentences literally, so a question phrased with
 * vocabulary the documents never use -- "what are the assessment weights",
 * when the syllabus only ever says "accounts for 40 percent of the course
 * grade" -- retrieves the right chunks and then still finds nothing to quote.
 * Suggesting one of those makes the demo look broken on its first click.
 *
 * They also span different topics (grading, staff, deadlines, contact) so the
 * first answer does not give the impression the system only indexes one
 * document.
 */
const SUGGESTED_QUESTIONS = [
  'What counts towards the final grade?',
  'When is the project proposal due?',
  'When are the office hours?',
  'Who is the TA?',
]

export const ChatPage: React.FC = () => {
  const { messages, isLoading, isStreaming, streamingContent, error, mode, sendMessage, stopStreaming, clearChat } =
    useChat()
  const { isRestoring } = useChatHistory()

  const busy = isLoading || isStreaming
  const isEmpty = messages.length === 0 && !streamingContent

  return (
    <div className="flex h-full flex-col bg-gray-50">
      <header className="flex items-center justify-between border-b bg-white px-4 py-3">
        <div className="flex items-center gap-3">
          <MessageSquare className="h-5 w-5 text-blue-600" aria-hidden="true" />
          <div>
            <h1 className="text-lg font-semibold text-gray-900">Course Chatbot</h1>
            <p className="text-xs text-gray-500">
              Answers are grounded in your uploaded documents
              <span className="ml-2">
                <ModeBadge mode={mode} />
              </span>
            </p>
          </div>
        </div>
        <button
          onClick={clearChat}
          disabled={isRestoring}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-50"
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
          Clear chat
        </button>
      </header>

      <MessageList
        messages={messages}
        isLoading={isLoading}
        streamingContent={streamingContent}
        isRestoring={isRestoring}
      />

      {isEmpty && !isRestoring && (
        <SuggestedQuestions
          questions={SUGGESTED_QUESTIONS}
          onSelect={sendMessage}
          disabled={busy}
        />
      )}

      {error && (
        <div
          role="alert"
          className="mx-4 mb-2 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <InputBox
        onSend={sendMessage}
        onStop={stopStreaming}
        disabled={busy}
        isStreaming={isStreaming}
      />
    </div>
  )
}
