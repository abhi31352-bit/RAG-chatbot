import React from 'react'
import {
  Activity,
  CheckCircle2,
  XCircle,
  Database,
  Layers,
  Cpu,
  Loader2,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react'
import type { HealthStatus, IndexStats, ReadinessStatus } from '../../types'

interface SystemStatusProps {
  health: HealthStatus | null
  readiness: ReadinessStatus | null
  stats: IndexStats | null
  isLoading: boolean
  error: string | null
  onRefresh: () => void
}

const CHECK_LABELS: Record<string, string> = {
  database: 'Database',
  vector_store: 'Vector store',
}

function CheckBadge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-sm">
      {ok ? (
        <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-green-500" aria-hidden="true" />
      ) : (
        <XCircle className="h-4 w-4 flex-shrink-0 text-red-500" aria-hidden="true" />
      )}
      <span className="text-gray-600">{label}</span>
      <span className="sr-only">{ok ? 'ready' : 'not ready'}</span>
    </span>
  )
}

function Row({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span className="flex items-center gap-2 text-sm text-gray-500">
        <span className="text-gray-400">{icon}</span>
        {label}
      </span>
      <span className="truncate font-mono text-sm text-gray-900">{value}</span>
    </div>
  )
}

/**
 * Backend and index state for the admin panel.
 *
 * The point of showing `indexed_with` next to `embedding_model` is that they
 * are allowed to disagree. When the embedding provider changes, the existing
 * index keeps the width it was built with while the service reports the new
 * one, and every subsequent upload is rejected with `EMBEDDING_MISMATCH` until
 * the old documents are deleted. Surfacing the mismatch here means the cause
 * is visible *before* the next upload fails, instead of only in an error.
 */
export const SystemStatus: React.FC<SystemStatusProps> = ({
  health,
  readiness,
  stats,
  isLoading,
  error,
  onRefresh,
}) => {
  const mismatch = !!stats?.indexed_with && !!stats.embedding_model && stats.indexed_with !== stats.embedding_model

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <Activity className="h-4 w-4 text-gray-400" aria-hidden="true" />
          System status
        </h2>
        <button
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
          aria-label="Refresh system status"
          className="flex items-center gap-1.5 text-xs text-gray-500 transition-colors hover:text-gray-700 disabled:opacity-50"
        >
          {isLoading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          Refresh
        </button>
      </div>

      {error && (
        <p role="alert" className="mb-3 flex items-start gap-1.5 text-xs text-amber-700">
          <AlertTriangle className="mt-px h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}

      {readiness && (
        <div className="mb-3 flex flex-wrap items-center gap-4 rounded-lg bg-gray-50 px-3 py-2">
          {Object.entries(readiness.checks).map(([key, ok]) => (
            <CheckBadge key={key} label={CHECK_LABELS[key] ?? key} ok={ok} />
          ))}
        </div>
      )}

      <div className="divide-y divide-gray-100">
        <Row
          icon={<Cpu className="h-4 w-4" aria-hidden="true" />}
          label="LLM model"
          value={health?.llm_model ?? '—'}
        />
        <Row
          icon={<Layers className="h-4 w-4" aria-hidden="true" />}
          label="Embedding model"
          value={stats?.embedding_model ?? '—'}
        />
        <Row
          icon={<Database className="h-4 w-4" aria-hidden="true" />}
          label="Indexed chunks"
          value={stats ? String(stats.total_chunks) : '—'}
        />
      </div>

      {mismatch && (
        <p className="mt-3 flex items-start gap-1.5 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <AlertTriangle className="mt-px h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
          <span>
            The index was built with <strong>{stats?.indexed_with}</strong> but the active model is{' '}
            <strong>{stats?.embedding_model}</strong>. Uploads will be rejected until the existing
            documents are deleted.
          </span>
        </p>
      )}
    </section>
  )
}
