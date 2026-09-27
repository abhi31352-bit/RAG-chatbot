import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MessageList } from './MessageList'
import { newMessageId } from '../../stores/chatStore'
import type { Message, Source } from '../../types'

const SOURCE: Source = {
  document_id: 'doc_1',
  filename: 'syllabus.txt',
  chunk_index: 0,
  excerpt: 'The final examination accounts for 40 percent.',
  similarity: 0.4213,
}

const message = (partial: Partial<Message>): Message => ({
  id: newMessageId(),
  role: 'assistant',
  content: '',
  sources: [],
  timestamp: new Date(),
  ...partial,
})

const userTurn = message({ role: 'user', content: 'What counts for the grade?' })

describe('MessageList', () => {
  it('shows the welcome state when there is nothing yet', () => {
    render(<MessageList messages={[]} isLoading={false} streamingContent="" />)

    expect(screen.getByText(/Welcome to the Course Chatbot/i)).toBeInTheDocument()
  })

  it('hides the welcome state while the first answer is pending', () => {
    render(<MessageList messages={[]} isLoading streamingContent="" />)

    expect(screen.queryByText(/Welcome to the Course Chatbot/i)).not.toBeInTheDocument()
  })

  it('shows the typing indicator before the first token arrives', () => {
    render(<MessageList messages={[userTurn]} isLoading streamingContent="" />)

    // The indicator has to appear on a follow-up turn too, not just when the
    // conversation is empty.
    expect(screen.getByRole('status', { name: /responding/i })).toBeInTheDocument()
  })

  it('shows the typing indicator on a follow-up turn', () => {
    render(<MessageList messages={[userTurn]} isLoading streamingContent="" />)

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('replaces the indicator with the streaming bubble once text arrives', () => {
    render(
      <MessageList
        messages={[userTurn]}
        isLoading
        streamingContent="The final exam is"
      />,
    )

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByTestId('streaming-bubble')).toHaveTextContent('The final exam is')
  })

  it('renders the streaming text as markdown, matching the finished state', () => {
    // Streaming raw text and then switching to markdown makes the typography
    // jump at the exact moment the answer completes.
    render(
      <MessageList
        messages={[]}
        isLoading
        streamingContent={'**40 percent** and `30 percent` homework'}
      />,
    )

    const bubble = screen.getByTestId('streaming-bubble')
    expect(bubble.querySelector('strong')).toHaveTextContent('40 percent')
    expect(bubble.querySelector('code')).toHaveTextContent('30 percent')
  })

  it('renders markdown in finished assistant messages', () => {
    render(
      <MessageList
        messages={[
          message({ content: '# Grading\n\n- Final: **40%**\n- Homework: 30%' }),
        ]}
        isLoading={false}
        streamingContent=""
      />,
    )

    expect(screen.getByRole('heading', { name: 'Grading' })).toBeInTheDocument()
    expect(screen.getByText('40%').tagName).toBe('STRONG')
  })

  it('renders a GFM table', () => {
    render(
      <MessageList
        messages={[
          message({
            content: '| Component | Weight |\n| --- | --- |\n| Final | 40% |',
          }),
        ]}
        isLoading={false}
        streamingContent=""
      />,
    )

    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Component' })).toBeInTheDocument()
  })

  it('lists sources under an answer', () => {
    render(
      <MessageList
        messages={[message({ content: 'The final exam is 40 percent.', sources: [SOURCE] })]}
        isLoading={false}
        streamingContent=""
      />,
    )

    const card = screen.getByTestId('source-card')
    expect(card).toHaveTextContent('syllabus.txt')
    expect(card).toHaveTextContent('chunk 0')
    expect(card).toHaveTextContent('42% match')
    expect(card).toHaveTextContent('The final examination accounts for 40 percent.')
  })

  it('omits the source section when there are none', () => {
    render(
      <MessageList
        messages={[message({ content: 'No context found.', sources: [] })]}
        isLoading={false}
        streamingContent=""
      />,
    )

    expect(screen.queryByTestId('source-card')).not.toBeInTheDocument()
    expect(screen.queryByText('Sources')).not.toBeInTheDocument()
  })

  it('shows a restoring notice when history is being loaded', () => {
    render(
      <MessageList messages={[]} isLoading={false} streamingContent="" isRestoring />,
    )

    expect(screen.getByText(/Restoring your conversation/i)).toBeInTheDocument()
    expect(screen.queryByText(/Welcome to the Course Chatbot/i)).not.toBeInTheDocument()
  })

  it('shows user text verbatim so typed markup stays visible', () => {
    render(
      <MessageList
        messages={[message({ role: 'user', content: 'What about **2+2**?' })]}
        isLoading={false}
        streamingContent=""
      />,
    )

    expect(screen.getByText('What about **2+2**?')).toBeInTheDocument()
  })
})
