import type { Source, StreamEvent } from '../types'

/**
 * Incremental parser for the `text/event-stream` responses from
 * `POST /api/chat/stream`.
 *
 * Pulled out of the service so it can be tested directly -- frame boundaries
 * land wherever the network happens to split a chunk, and that is precisely
 * the part that is hard to get right by inspection.
 *
 * The parser is deliberately lenient. A malformed frame is counted and skipped
 * rather than thrown: one bad frame should cost a few words of the answer, not
 * the whole stream plus an opaque error.
 */
export class SSEParser {
  private buffer = ''
  private malformed = 0

  /** Frames skipped so far because their payload would not parse as JSON. */
  get malformedCount(): number {
    return this.malformed
  }

  /** Feed the next chunk of decoded text; returns any complete frames. */
  push(chunk: string): StreamEvent[] {
    this.buffer += chunk
    const events: StreamEvent[] = []
    // Keep the trailing partial line in the buffer: a network chunk can land
    // anywhere, including the middle of a frame's JSON.
    const lines = this.buffer.split('\n')
    this.buffer = lines.pop() ?? ''
    for (const line of lines) {
      const event = this.parseLine(line)
      if (event) events.push(event)
    }
    return events
  }

  /**
   * Parse whatever is left once the stream ends. A server that closes without
   * a trailing newline would otherwise lose its final frame.
   */
  flush(): StreamEvent[] {
    const remainder = this.buffer
    this.buffer = ''
    const event = remainder ? this.parseLine(remainder) : null
    return event ? [event] : []
  }

  private parseLine(line: string): StreamEvent | null {
    const trimmed = line.replace(/\r$/, '').trim()
    // Blank lines separate frames; a leading colon marks a comment/heartbeat.
    if (!trimmed || trimmed.startsWith(':')) return null
    if (!trimmed.startsWith('data:')) return null

    const payload = trimmed.slice(5).trim()
    if (!payload) return null

    let parsed: unknown
    try {
      parsed = JSON.parse(payload)
    } catch {
      this.malformed += 1
      return null
    }
    if (typeof parsed !== 'object' || parsed === null) {
      this.malformed += 1
      return null
    }
    return toStreamEvent(parsed as Record<string, unknown>)
  }
}

function toStreamEvent(payload: Record<string, unknown>): StreamEvent {
  return {
    delta: typeof payload.delta === 'string' ? payload.delta : '',
    finish: payload.finish === true,
    sources: Array.isArray(payload.sources) ? (payload.sources as Source[]) : [],
    session_id: typeof payload.session_id === 'string' ? payload.session_id : null,
    mode: typeof payload.mode === 'string' ? payload.mode : null,
    error: typeof payload.error === 'string' ? payload.error : null,
  }
}
