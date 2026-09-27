import React, { useEffect, useRef, useState } from 'react'
import { Loader2, Send, Square } from 'lucide-react'

interface InputBoxProps {
  onSend: (message: string) => void
  onStop?: () => void
  disabled?: boolean
  isStreaming?: boolean
  placeholder?: string
}

const MAX_HEIGHT = 200

export const InputBox: React.FC<InputBoxProps> = ({
  onSend,
  onStop,
  disabled = false,
  isStreaming = false,
  placeholder = 'Ask a question about the course material...',
}) => {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Grow with the content up to a cap, then scroll. Resetting to 'auto' first
  // is what makes the height shrink again when text is deleted.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`
  }, [input])

  const submit = () => {
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      aria-label="Ask a question"
      className="flex items-end gap-2 border-t bg-white p-4"
    >
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        aria-label="Your question"
        className="max-h-[200px] flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
      />

      {isStreaming && onStop ? (
        <button
          type="button"
          onClick={onStop}
          title="Stop generating"
          aria-label="Stop generating"
          className="rounded-xl bg-gray-700 p-2 text-white transition-colors hover:bg-gray-800"
        >
          <Square className="h-5 w-5" />
        </button>
      ) : (
        <button
          type="submit"
          disabled={disabled || !input.trim()}
          aria-label="Send"
          className="rounded-xl bg-blue-600 p-2 text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
        >
          {disabled ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Send className="h-5 w-5" />
          )}
        </button>
      )}
    </form>
  )
}
