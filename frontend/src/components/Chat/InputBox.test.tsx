import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { InputBox } from './InputBox'

describe('InputBox', () => {
  it('sends the trimmed text and clears the field', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<InputBox onSend={onSend} />)

    const box = screen.getByLabelText('Your question')
    await user.type(box, '  When are office hours?  ')
    await user.click(screen.getByLabelText('Send'))

    expect(onSend).toHaveBeenCalledWith('When are office hours?')
    expect(box).toHaveValue('')
  })

  it('sends on Enter', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<InputBox onSend={onSend} />)

    await user.type(screen.getByLabelText('Your question'), 'Question{Enter}')

    expect(onSend).toHaveBeenCalledWith('Question')
  })

  it('inserts a newline on Shift+Enter instead of sending', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<InputBox onSend={onSend} />)

    const box = screen.getByLabelText('Your question')
    await user.type(box, 'Line one{Shift>}{Enter}{/Shift}Line two')

    expect(onSend).not.toHaveBeenCalled()
    expect(box).toHaveValue('Line one\nLine two')
  })

  it('does not send while an IME composition is active', async () => {
    // Enter commits a candidate in a CJK input method; treating that as a send
    // would truncate the word the user was in the middle of typing.
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<InputBox onSend={onSend} />)

    const box = screen.getByLabelText('Your question')
    await user.type(box, '日本語')
    await user.keyboard('{Enter}')

    // jsdom does not model composition, so drive the flag directly.
    expect(onSend).toHaveBeenCalled()
    onSend.mockClear()

    const fireComposition = (isComposing: boolean) => {
      const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
      Object.defineProperty(event, 'isComposing', { value: isComposing })
      box.dispatchEvent(event)
    }
    box.focus()
    fireComposition(true)
    expect(onSend).not.toHaveBeenCalled()
  })

  it('will not send a whitespace-only question', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<InputBox onSend={onSend} />)

    await user.type(screen.getByLabelText('Your question'), '   ')
    expect(screen.getByLabelText('Send')).toBeDisabled()
    expect(onSend).not.toHaveBeenCalled()
  })

  it('disables the input while busy', () => {
    render(<InputBox onSend={vi.fn()} disabled />)
    expect(screen.getByLabelText('Your question')).toBeDisabled()
  })

  it('offers a stop control instead of send while streaming', async () => {
    const user = userEvent.setup()
    const onStop = vi.fn()
    render(<InputBox onSend={vi.fn()} onStop={onStop} isStreaming disabled />)

    expect(screen.queryByLabelText('Send')).not.toBeInTheDocument()
    await user.click(screen.getByLabelText('Stop generating'))
    expect(onStop).toHaveBeenCalled()
  })

  it('grows with the content', async () => {
    const user = userEvent.setup()
    render(<InputBox onSend={vi.fn()} />)
    const box = screen.getByLabelText('Your question') as HTMLTextAreaElement

    await user.type(box, 'line one{Shift>}{Enter}{/Shift}line two{Shift>}{Enter}{/Shift}line three')

    // jsdom reports scrollHeight as 0, so assert the mechanism: the height is
    // rewritten from 'auto' rather than left to grow unbounded.
    expect(box.style.height).not.toBe('')
  })

  it('labels the field for screen readers', () => {
    render(<InputBox onSend={vi.fn()} />)
    expect(within(screen.getByRole('form')).getByLabelText('Your question')).toBeInTheDocument()
  })
})
