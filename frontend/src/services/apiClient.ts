import axios, { AxiosError } from 'axios'

/**
 * Base URL for every API call.
 *
 * Defaults to the relative `/api`, which the Vite dev proxy forwards to the
 * backend. That keeps the browser on a single origin and CORS out of the
 * picture entirely.
 */
export const API_BASE_URL: string = import.meta.env.VITE_API_URL || '/api'

/** An error carrying the backend's machine-readable code alongside the text. */
export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: unknown

  constructor(message: string, code: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * Unwrap the backend's error envelope.
 *
 * The API returns `{"error": {code, message, details}}` (architecture.md 5.3),
 * *not* FastAPI's default `{"detail": ...}`. Reading `detail` alone would
 * silently discard every real error message and leave the user staring at
 * "Request failed with status code 500".
 */
function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ error?: { code?: string; message?: string; details?: unknown } }>
    const status = axiosError.response?.status ?? 0
    const envelope = axiosError.response?.data?.error

    if (envelope?.message) {
      return new ApiError(envelope.message, envelope.code ?? 'UNKNOWN', status, envelope.details)
    }

    // A response without our envelope means something upstream of the
    // exception handlers answered: a proxy, or a 404 from a wrong base URL.
    if (axiosError.response) {
      const detail = (axiosError.response.data as { detail?: string } | undefined)?.detail
      return new ApiError(
        detail || `Request failed with status ${status}`,
        'HTTP_ERROR',
        status,
      )
    }

    // No response at all: the server is down, or the request was aborted.
    if (axiosError.code === 'ERR_CANCELED') {
      return new ApiError('Request cancelled', 'CANCELLED', 0)
    }
    return new ApiError(axiosError.message || 'Cannot reach the server', 'NETWORK_ERROR', 0)
  }

  return new ApiError(error instanceof Error ? error.message : 'An error occurred', 'UNKNOWN', 0)
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(toApiError(error)),
)
