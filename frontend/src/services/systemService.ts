import { apiClient } from './apiClient'
import type { HealthStatus, ReadinessStatus } from '../types'

export type { HealthStatus, ReadinessStatus } from '../types'

/**
 * Liveness and readiness of the backend, for the admin panel's status card.
 *
 * These are the only two read-only endpoints that describe the server's own
 * state rather than the data in it, which is why the status panel is built on
 * them instead of on the chat endpoints.
 */
export const systemService = {
  async health(): Promise<HealthStatus> {
    const response = await apiClient.get<HealthStatus>('/health')
    return response.data
  },

  async ready(): Promise<ReadinessStatus> {
    const response = await apiClient.get<ReadinessStatus>('/health/ready')
    return response.data
  },
}
