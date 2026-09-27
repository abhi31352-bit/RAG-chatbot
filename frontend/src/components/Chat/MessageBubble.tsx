import React from 'react'
import type { Message } from '../../types'
import { MarkdownContent } from './MarkdownContent'
import { SourceCard } from './SourceCard'

interface MessageBubbleProps {
  message: Message
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user'

  return (
    <div className={`mb-4 flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] md:max-w-[75%] ${isUser ? 'order-2' : 'order-1'}`}>
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'rounded-br-md bg-blue-600 text-white'
              : 'rounded-bl-md border border-gray-200 bg-white text-gray-900'
          }`}
        >
          {isUser ? (
            // User text is shown verbatim: rendering it as markdown would let
            // typed asterisks vanish instead of appearing as characters.
            <p className="whitespace-pre-wrap text-sm">{message.content}</p>
          ) : (
            <MarkdownContent>{message.content}</MarkdownContent>
          )}
        </div>

        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 space-y-1">
            <p className="px-1 text-[11px] font-medium uppercase tracking-wide text-gray-400">
              Sources
            </p>
            {message.sources.map((source) => (
              <SourceCard key={`${source.document_id}:${source.chunk_index}`} source={source} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
