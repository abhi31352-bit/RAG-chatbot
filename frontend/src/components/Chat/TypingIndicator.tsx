import React from 'react'

export const TypingIndicator: React.FC = () => (
  <div className="mb-4 flex justify-start" role="status" aria-label="Assistant is responding">
    <div className="rounded-2xl rounded-bl-md border border-gray-200 bg-white px-4 py-3">
      <div className="flex space-x-1">
        <div
          className="h-2 w-2 animate-bounce rounded-full bg-gray-400"
          style={{ animationDelay: '0ms' }}
        />
        <div
          className="h-2 w-2 animate-bounce rounded-full bg-gray-400"
          style={{ animationDelay: '150ms' }}
        />
        <div
          className="h-2 w-2 animate-bounce rounded-full bg-gray-400"
          style={{ animationDelay: '300ms' }}
        />
      </div>
    </div>
  </div>
)
