import { describe, expect, it, vi, beforeEach } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'
import { ApiError, apiClient, API_BASE_URL } from './apiClient'

/** Build an AxiosError shaped the way axios rejects with. */
function axiosErrorWith(status: number, data: unknown): AxiosError {
  const error = new AxiosError('Request failed with status code ' + status)
  error.response = {
    status,
    statusText: 'Error',
    data,
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  }
  return error
}

/** Run the response interceptor's rejection path and return what it threw. */
async function rejectionOf(error: unknown): Promise<unknown> {
  const handler = apiClient.interceptors.response.handlers?.find((h) => h && h.rejected)
  if (!handler?.rejected) throw new Error('no rejection interceptor registered')
  try {
    await handler.rejected(error)
    return null
  } catch (thrown) {
    return thrown
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('API_BASE_URL', () => {
  it('falls back to the relative /api so the dev proxy handles it', () => {
    // Absolute base URLs would make the browser hit the backend cross-origin
    // and drag CORS into a project that does not need it.
    expect(API_BASE_URL).toBe('/api')
  })
})

describe('error envelope handling', () => {
  it("reads the backend's error.message, not FastAPI's detail", async () => {
    // The API returns {"error": {code, message, details}}. Reading `detail`
    // would discard every real message and show a bare status code instead.
    const thrown = await rejectionOf(
      axiosErrorWith(404, {
        error: {
          code: 'DOCUMENT_NOT_FOUND',
          message: 'Document doc_abc was not found',
          details: { document_id: 'doc_abc' },
        },
      }),
    )

    expect(thrown).toBeInstanceOf(ApiError)
    const apiError = thrown as ApiError
    expect(apiError.message).toBe('Document doc_abc was not found')
    expect(apiError.code).toBe('DOCUMENT_NOT_FOUND')
    expect(apiError.status).toBe(404)
    expect(apiError.details).toEqual({ document_id: 'doc_abc' })
  })

  it('surfaces the specific message for a 409 embedding mismatch', async () => {
    const thrown = await rejectionOf(
      axiosErrorWith(409, {
        error: {
          code: 'EMBEDDING_MISMATCH',
          message: 'The index was built with local-hash-512, but the active model is text-embedding-3-small',
          details: {},
        },
      }),
    )

    expect((thrown as ApiError).message).toContain('local-hash-512')
  })

  it('falls back to FastAPI detail when the response is not our envelope', async () => {
    const thrown = await rejectionOf(axiosErrorWith(422, { detail: 'field required' }))

    expect((thrown as ApiError).message).toBe('field required')
    expect((thrown as ApiError).code).toBe('HTTP_ERROR')
  })

  it('names the status when the body is unreadable', async () => {
    const thrown = await rejectionOf(axiosErrorWith(502, '<html>bad gateway</html>'))

    expect((thrown as ApiError).message).toBe('Request failed with status 502')
  })

  it('reports an unreachable server as a network error, not a crash', async () => {
    const error = new AxiosError('Network Error')
    const thrown = await rejectionOf(error)

    expect((thrown as ApiError).code).toBe('NETWORK_ERROR')
    expect((thrown as ApiError).message).toBe('Network Error')
  })

  it('distinguishes a cancelled request from a failure', async () => {
    const error = new AxiosError('canceled')
    error.code = 'ERR_CANCELED'
    const thrown = await rejectionOf(error)

    expect((thrown as ApiError).code).toBe('CANCELLED')
  })

  it('handles a non-axios rejection', async () => {
    const thrown = await rejectionOf(new TypeError('boom'))

    expect((thrown as ApiError).message).toBe('boom')
    expect((thrown as ApiError).code).toBe('UNKNOWN')
  })

  it('passes an existing ApiError straight through', async () => {
    const original = new ApiError('already typed', 'LLM_UNAVAILABLE', 503)
    expect(await rejectionOf(original)).toBe(original)
  })
})
