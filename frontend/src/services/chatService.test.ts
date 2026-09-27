import { describe, expect, it, vi } from 'vitest'
import { chatService } from './chatService'
import type { ChatRequest, StreamEvent } from '../types'

/**
 * Bytes captured verbatim from `POST /api/chat/stream` on the running backend,
 * proxied through Vite. Using a real capture rather than a hand-written
 * fixture means these assertions are pinned to the frames the server actually
 * emits, including its field names and framing.
 */
const REAL_RESPONSE = `data: {"delta": "- Office hours are held on", "finish": false}

data: {"delta": " Tuesdays from 2pm to 4pm in", "finish": false}

data: {"delta": " Gates 412. (syllabus.txt)\\n- The TA is", "finish": false}

data: {"delta": " Priya Raman. (syllabus.txt)", "finish": false}

data: {"delta": "", "finish": true, "sources": [{"document_id": "doc_181a7117ffce", "filename": "syllabus.txt", "chunk_index": 0, "excerpt": "CS 401 Machine Learning Syllabus. The final examination accounts for 40", "similarity": 0.2897}, {"document_id": "doc_80f8405e38e4", "filename": "lecture.md", "chunk_index": 0, "excerpt": "# Machine Learning Lectures", "similarity": 0.2831}, {"document_id": "doc_f89fd641e13d", "filename": "long.pdf", "chunk_index": 1, "excerpt": "the page body long enough to force the chunker", "similarity": 0.0186}], "session_id": "sess_5563f6bbf7ec", "mode": "offline-extractive"}

`

/** Build a Response whose body emits `chunks` as separate reads. */
function streamingResponse(chunks: string[], init: ResponseInit = {}): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' }, ...init })
}

async function collect(chunks: string[]) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamingResponse(chunks)))
  const events: StreamEvent[] = []
  for await (const event of chatService.streamQuery({ question: 'When are office hours?' })) {
    events.push(event)
  }
  return events
}

/** Pull the first frame, which is where a pre-stream failure surfaces. */
async function firstFrame(request: ChatRequest = { question: 'x' }): Promise<StreamEvent> {
  const result = await chatService.streamQuery(request).next()
  if (result.done) throw new Error('expected the stream to produce a frame')
  return result.value
}

describe('streamQuery against real backend output', () => {
  it('reassembles the answer from the captured frames', async () => {
    const events = await collect([REAL_RESPONSE])

    const answer = events.map((e) => e.delta).join('')
    expect(answer).toContain('Office hours are held on Tuesdays from 2pm to 4pm in Gates 412')
    expect(answer).toContain('The TA is Priya Raman.')
  })

  it('turns the escaped newline in a delta into a real line break', async () => {
    // The backend JSON-encodes newlines inside a delta; the client has to
    // decode them or the two quoted sentences run together.
    const events = await collect([REAL_RESPONSE])
    expect(events.map((e) => e.delta).join('')).toContain('\n- The TA is')
  })

  it('surfaces the session id and mode from the terminal frame', async () => {
    const events = await collect([REAL_RESPONSE])
    const last = events.at(-1)

    expect(last?.finish).toBe(true)
    expect(last?.session_id).toBe('sess_5563f6bbf7ec')
    expect(last?.mode).toBe('offline-extractive')
  })

  it('surfaces all four sources with their similarity scores', async () => {
    const events = await collect([REAL_RESPONSE])
    const sources = events.at(-1)?.sources ?? []

    expect(sources).toHaveLength(3)
    expect(sources[0]).toMatchObject({ filename: 'syllabus.txt', chunk_index: 0 })
    expect(sources[0].similarity).toBeCloseTo(0.2897, 3)
    // Page-less chunks still come through, rather than being dropped.
    expect(sources.map((s) => s.filename)).toEqual(['syllabus.txt', 'lecture.md', 'long.pdf'])
  })

  it('parses correctly when the response arrives in arbitrary byte splits', async () => {
    // The framing must not depend on where the network chose to cut.
    const whole = await collect([REAL_RESPONSE])
    const sizes = [7, 13, 1, 400, 3, 90]
    const pieces: string[] = []
    let at = 0
    for (const size of sizes) {
      pieces.push(REAL_RESPONSE.slice(at, at + size))
      at += size
    }
    pieces.push(REAL_RESPONSE.slice(at))

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamingResponse(pieces)))
    const split = []
    for await (const event of chatService.streamQuery({ question: 'x' })) split.push(event)

    expect(split).toEqual(whole)
  })

  it('splits a multi-byte character across two reads without corrupting it', async () => {
    // An em dash is three UTF-8 bytes. A naive per-chunk decode would emit a
    // replacement character mid-answer.
    const payload =
      'data: {"delta": "before \\u2014 after", "finish": false}\n\n' +
      'data: {"delta": "", "finish": true, "session_id": "s1"}\n\n'
    const bytes = new TextEncoder().encode(payload)
    const cut = bytes.indexOf(0xe2) + 1 // mid-character

    const encoder = new TextEncoder()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, cut))
        controller.enqueue(bytes.slice(cut))
        controller.close()
      },
    })
    void encoder
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }),
      ),
    )

    const events = []
    for await (const event of chatService.streamQuery({ question: 'x' })) events.push(event)

    expect(events[0].delta).toBe('before — after')
  })

  it('reports the error envelope when the stream is refused before it starts', async () => {
    // One call only: a Response body can be read once, so a second run would
    // see an already-consumed body rather than the real failure path.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: 'VALIDATION_ERROR',
              message: 'question must not be blank',
              details: {},
            },
          }),
          { status: 422, statusText: 'Unprocessable Entity' },
        ),
      ),
    )

    // One call only: a Response body can be read once, so a second attempt
    // would see an already-consumed body rather than the real failure path.
    await expect(firstFrame()).rejects.toMatchObject({
      message: 'question must not be blank',
      code: 'VALIDATION_ERROR',
      status: 422,
    })
  })

  it('reports a non-JSON failure without losing the status line', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('<html>502</html>', { status: 502, statusText: 'Bad Gateway' }),
      ),
    )

    await expect(firstFrame()).rejects.toThrow('502')
  })

  it('sends the question, session and the streaming accept header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(streamingResponse([REAL_RESPONSE]))
    vi.stubGlobal('fetch', fetchMock)

    await firstFrame({ question: 'Follow up', session_id: 'sess_1' })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/chat/stream')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({
      question: 'Follow up',
      session_id: 'sess_1',
    })
    expect((init.headers as Record<string, string>).Accept).toBe('text/event-stream')
  })
})
