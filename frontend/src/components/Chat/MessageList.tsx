import React from 'react'
import type { Message } from '../../types'
import { MarkdownContent } from './MarkdownContent'
import { MessageBubble } from './MessageBubble'
import { TypingIndicator } from './TypingIndicator'

interface MessageListProps {
  messages: Message[]
  isLoading: boolean
  streamingContent: string
  isRestoring?: boolean
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isLoading,
  streamingContent,
  isRestoring = false,
}) => {
  const bottomRef = React.useRef<HTMLDivElement>(null)
  const showEmpty = messages.length === 0 && !isLoading && !isRestoring
  // The indicator covers the wait for the first token, not the whole answer.
  // Keying it off `isStreaming` instead would hide it entirely: that flag is
  // set before the first token arrives.
  const showTyping = isLoading && !streamingContent
  const showStreaming = Boolean(streamingContent)

  React.useEffect(() => {
    // Optional call: scrollIntoView is absent in jsdom and in some embedded
    // webviews, and auto-scroll is a nicety, not a reason to crash the chat.
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [messages, streamingContent])

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      {showEmpty && (
        <div className="flex h-full flex-col items-center justify-center text-center text-gray-400">
          <p className="text-lg font-medium text-gray-600">Welcome to the Course Chatbot</p>
          <p className="mt-1 max-w-sm text-sm">
            Ask a question and the answer is grounded in the documents you have uploaded, with the
            sources it used.
          </p>
        </div>
      )}

      {isRestoring && messages.length === 0 && (
        <p className="py-2 text-center text-sm text-gray-400">Restoring your conversation…</p>
      )}

      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}

      {showTyping && <TypingIndicator />}

      {showStreaming && (
        <div className="mb-4 flex justify-start" data-testid="streaming-bubble">
          <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-gray-200 bg-white px-4 py-3 md:max-w-[75%]">
            <MarkdownContent>{streamingContent}</MarkdownContent>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
