import { describe, expect, it } from 'vitest'
import { SSEParser } from './sse'
import type { Source } from '../types'

const SOURCE: Source = {
  document_id: 'doc_1',
  filename: 'syllabus.txt',
  chunk_index: 0,
  excerpt: 'The final exam is worth 40 percent.',
  similarity: 0.42,
}

/** The exact framing the backend's `_frame` produces. */
const frame = (payload: Record<string, unknown>) => `data: ${JSON.stringify(payload)}\n\n`

describe('SSEParser', () => {
  it('parses a single complete frame', () => {
    const parser = new SSEParser()
    const events = parser.push(frame({ delta: 'Hello', finish: false }))

    expect(events).toHaveLength(1)
    expect(events[0].delta).toBe('Hello')
    expect(events[0].finish).toBe(false)
  })

  it('parses several frames arriving in one chunk', () => {
    const parser = new SSEParser()
    const events = parser.push(
      frame({ delta: 'One', finish: false }) + frame({ delta: 'Two', finish: false }),
    )

    expect(events.map((e) => e.delta)).toEqual(['One', 'Two'])
  })

  it('carries sources on the terminal frame', () => {
    const parser = new SSEParser()
    const events = parser.push(
      frame({ delta: '', finish: true, sources: [SOURCE], session_id: 'sess_1', mode: 'openai' }),
    )

    expect(events[0].sources).toEqual([SOURCE])
    expect(events[0].session_id).toBe('sess_1')
    expect(events[0].mode).toBe('openai')
  })

  it('surfaces a mid-stream error frame', () => {
    // A failure after the headers are sent arrives as a terminal frame, not an
    // HTTP status. Dropping it would render an empty answer with no message.
    const parser = new SSEParser()
    const events = parser.push(frame({ delta: '', finish: true, error: 'LLM unavailable' }))

    expect(events[0].error).toBe('LLM unavailable')
    expect(events[0].finish).toBe(true)
  })

  it('defaults every optional field when the payload is sparse', () => {
    const parser = new SSEParser()
    const [event] = parser.push(frame({ delta: 'x' }))

    expect(event).toEqual({
      delta: 'x',
      finish: false,
      sources: [],
      session_id: null,
      mode: null,
      error: null,
    })
  })

  describe('frames split across chunks', () => {
    it('waits for the rest of a partially received frame', () => {
      const parser = new SSEParser()
      const whole = frame({ delta: 'Hello there', finish: false })

      // Cut in the middle of the JSON payload.
      const cut = Math.floor(whole.length / 2)
      expect(parser.push(whole.slice(0, cut))).toHaveLength(0)
      expect(parser.push(whole.slice(cut))).toHaveLength(1)
    })

    it('reassembles a frame delivered one character at a time', () => {
      const parser = new SSEParser()
      const whole = frame({ delta: 'A', finish: true, session_id: 's1' })

      const events = whole.split('').flatMap((char) => parser.push(char))

      expect(events).toHaveLength(1)
      expect(events[0].delta).toBe('A')
      expect(events[0].session_id).toBe('s1')
    })
  })

  it('flush() parses a trailing frame the server never newline-terminated', () => {
    const parser = new SSEParser()
    // No trailing newline: the last frame is still sitting in the buffer.
    expect(parser.push('data: {"delta":"last","finish":true}')).toHaveLength(0)

    const flushed = parser.flush()
    expect(flushed).toHaveLength(1)
    expect(flushed[0].delta).toBe('last')
  })

  it('flush() on an empty buffer yields nothing', () => {
    expect(new SSEParser().flush()).toEqual([])
  })

  it('ignores blank separators, heartbeats and comments', () => {
    const parser = new SSEParser()
    const events = parser.push(`\n\n: keep-alive\n\n${frame({ delta: 'real', finish: false })}`)

    expect(events).toHaveLength(1)
    expect(events[0].delta).toBe('real')
  })

  it('accepts a frame without the space after "data:"', () => {
    const parser = new SSEParser()
    const events = parser.push('data:{"delta":"tight","finish":false}\n\n')

    expect(events[0].delta).toBe('tight')
  })

  it('tolerates CRLF line endings', () => {
    const parser = new SSEParser()
    const events = parser.push('data: {"delta":"crlf","finish":false}\r\n\r\n')

    expect(events[0].delta).toBe('crlf')
  })

  describe('malformed frames', () => {
    it('skips unparseable JSON and keeps going', () => {
      const parser = new SSEParser()
      const events = parser.push(
        `data: {not json}\n\n${frame({ delta: 'recovered', finish: false })}`,
      )

      expect(events).toHaveLength(1)
      expect(events[0].delta).toBe('recovered')
      expect(parser.malformedCount).toBe(1)
    })

    it('skips a valid JSON payload that is not an object', () => {
      const parser = new SSEParser()
      const events = parser.push('data: "just a string"\n\ndata: 42\n\n')

      expect(events).toHaveLength(0)
      expect(parser.malformedCount).toBe(2)
    })

    it('skips an empty data field', () => {
      const parser = new SSEParser()
      expect(parser.push('data: \n\n')).toHaveLength(0)
      expect(parser.malformedCount).toBe(0)
    })

    it('ignores lines that are not data frames', () => {
      const parser = new SSEParser()
      expect(parser.push('event: message\nid: 7\n\n')).toHaveLength(0)
    })
  })

  it('ignores non-string deltas instead of rendering them', () => {
    const parser = new SSEParser()
    const [event] = parser.push(frame({ delta: { nested: true }, finish: 'yes' }))

    expect(event.delta).toBe('')
    expect(event.finish).toBe(false)
  })
})
