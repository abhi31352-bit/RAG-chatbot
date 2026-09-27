import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SystemStatus } from './SystemStatus'
import type { HealthStatus, IndexStats, ReadinessStatus } from '../../types'

const HEALTH: HealthStatus = {
  status: 'healthy',
  app_name: 'RAG Chatbot',
  environment: 'development',
  llm_model: 'big-pickle',
}

const STATS: IndexStats = {
  collection_name: 'course_documents',
  total_chunks: 12,
  embedding_provider: 'local',
  embedding_model: 'local-hash-2048',
  indexed_with: 'local-hash-2048',
}

const READY: ReadinessStatus = {
  ready: true,
  checks: { database: true, vector_store: true },
}

function renderStatus(overrides: Partial<Parameters<typeof SystemStatus>[0]> = {}) {
  const onRefresh = vi.fn()
  const props = {
    health: HEALTH,
    readiness: READY,
    stats: STATS,
    isLoading: false,
    error: null,
    onRefresh,
    ...overrides,
  }
  return { onRefresh, ...render(<SystemStatus {...props} />) }
}

describe('SystemStatus', () => {
  it('reports the model, embeddings and chunk count', () => {
    renderStatus()
    expect(screen.getByText('big-pickle')).toBeInTheDocument()
    expect(screen.getByText('local-hash-2048')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
  })

  it('marks each readiness check', () => {
    renderStatus()
    expect(screen.getByText('Database')).toBeInTheDocument()
    expect(screen.getByText('Vector store')).toBeInTheDocument()
  })

  it('flags a failing readiness check', () => {
    renderStatus({ readiness: { ready: false, checks: { database: true, vector_store: false } } })
    expect(screen.getByText('not ready')).toBeInTheDocument()
  })

  it('explains an embedding mismatch before the next upload hits it', () => {
    // Changing the provider leaves the index on its old width, and every
    // upload is then rejected with EMBEDDING_MISMATCH. Showing it here means
    // the cause is visible in advance.
    renderStatus({ stats: { ...STATS, embedding_model: 'text-embedding-3-small', indexed_with: 'local-hash-512' } })

    const warning = screen.getByText(/The index was built with/)
    expect(warning).toHaveTextContent('local-hash-512')
    expect(warning).toHaveTextContent('text-embedding-3-small')
    expect(warning).toHaveTextContent('Uploads will be rejected')
  })

  it('shows no mismatch warning when the index matches the active model', () => {
    renderStatus()
    expect(screen.queryByText(/The index was built with/)).not.toBeInTheDocument()
  })

  it('does not claim a mismatch when nothing is indexed yet', () => {
    // indexed_with is null on an empty index, which is not a disagreement.
    renderStatus({ stats: { ...STATS, indexed_with: null } })
    expect(screen.queryByText(/The index was built with/)).not.toBeInTheDocument()
  })

  it('surfaces a status read failure', () => {
    renderStatus({ error: 'Network Error' })
    expect(screen.getByRole('alert')).toHaveTextContent('Network Error')
  })

  it('falls back to a dash while the panel has no data', () => {
    renderStatus({ health: null, readiness: null, stats: null, isLoading: true })
    expect(screen.getAllByText('—')).toHaveLength(3)
  })

  it('refreshes on request', async () => {
    const user = userEvent.setup()
    const { onRefresh } = renderStatus()

    await user.click(screen.getByRole('button', { name: 'Refresh system status' }))

    expect(onRefresh).toHaveBeenCalled()
  })

  it('disables refresh while loading', () => {
    renderStatus({ isLoading: true })
    expect(screen.getByRole('button', { name: 'Refresh system status' })).toBeDisabled()
  })
})
