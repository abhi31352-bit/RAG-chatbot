import { useCallback, useEffect, useState } from 'react'
import { documentService } from '../services/documentService'
import { systemService } from '../services/systemService'
import type { HealthStatus, IndexStats, ReadinessStatus } from '../types'

export interface SystemStatus {
  health: HealthStatus | null
  readiness: ReadinessStatus | null
  stats: IndexStats | null
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

/**
 * Backend health plus vector-store statistics.
 *
 * The three requests are independent, and failing one must not blank out the
 * other two: a panel that renders nothing unless every call succeeds hides the
 * very thing it exists to show. Each is settled separately and `error`
 * accumulates the failures, so a database outage still lets the panel report
 * that the vector store is up.
 */
export function useSystemStatus(): SystemStatus {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [readiness, setReadiness] = useState<ReadinessStatus | null>(null)
  const [stats, setStats] = useState<IndexStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    const [healthResult, readyResult, statsResult] = await Promise.allSettled([
      systemService.health(),
      systemService.ready(),
      documentService.stats(),
    ])

    if (healthResult.status === 'fulfilled') setHealth(healthResult.value)
    if (readyResult.status === 'fulfilled') setReadiness(readyResult.value)
    if (statsResult.status === 'fulfilled') setStats(statsResult.value)

    // Report the first failure but keep whatever did answer, so one broken
    // endpoint does not blank the panel.
    const failure = [healthResult, readyResult, statsResult].find(
      (result) => result.status === 'rejected',
    ) as PromiseRejectedResult | undefined
    if (failure) {
      setError(
        failure.reason instanceof Error && failure.reason.message
          ? failure.reason.message
          : 'Could not read the backend status.',
      )
    }

    setIsLoading(false)
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return { health, readiness, stats, isLoading, error, refresh }
}
