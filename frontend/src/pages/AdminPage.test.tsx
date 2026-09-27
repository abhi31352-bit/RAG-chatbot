import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AdminPage } from './AdminPage'
import { documentService } from '../services/documentService'
import { systemService } from '../services/systemService'
import { resetDocumentStore } from '../stores/documentStore'
import { ApiError } from '../services/apiClient'
import type { Document, IndexStats } from '../types'

vi.mock('../services/documentService', () => ({
  documentService: {
    list: vi.fn(),
    upload: vi.fn(),
    remove: vi.fn(),
    stats: vi.fn(),
  },
}))

vi.mock('../services/systemService', () => ({
  systemService: {
    health: vi.fn(),
    ready: vi.fn(),
  },
}))

const list = vi.mocked(documentService.list)
const upload = vi.mocked(documentService.upload)
const remove = vi.mocked(documentService.remove)
const stats = vi.mocked(documentService.stats)
const health = vi.mocked(systemService.health)
const ready = vi.mocked(systemService.ready)

const DOC: Document = {
  id: 'doc_1',
  filename: 'syllabus.txt',
  file_type: 'txt',
  file_size: 2048,
  chunk_count: 3,
  status: 'processed',
  created_at: '2026-03-04T10:00:00Z',
}

const STATS: IndexStats = {
  collection_name: 'course_documents',
  total_chunks: 3,
  embedding_provider: 'local',
  embedding_model: 'local-hash-2048',
  indexed_with: 'local-hash-2048',
}

beforeEach(() => {
  vi.clearAllMocks()
  resetDocumentStore()
  list.mockResolvedValue({ documents: [DOC], total: 1 })
  upload.mockResolvedValue(DOC)
  remove.mockResolvedValue(undefined)
  stats.mockResolvedValue(STATS)
  health.mockResolvedValue({
    status: 'healthy',
    app_name: 'RAG Chatbot',
    environment: 'development',
    llm_model: 'big-pickle',
  })
  ready.mockResolvedValue({ ready: true, checks: { database: true, vector_store: true } })
})

/** AdminPage sits behind the router in the real app, so render it in one. */
function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/admin']}>
      <Routes>
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AdminPage', () => {
  it('loads and displays the uploaded documents', async () => {
    renderPage()
    expect(await screen.findByText('syllabus.txt')).toBeInTheDocument()
    expect(screen.getByText('1 document uploaded')).toBeInTheDocument()
  })

  it('shows the system status', async () => {
    renderPage()
    expect(await screen.findByText('big-pickle')).toBeInTheDocument()
    expect(screen.getByText('local-hash-2048')).toBeInTheDocument()
  })

  it('uploads a file end to end and lists it', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('syllabus.txt')

    const lecture: Document = { ...DOC, id: 'doc_2', filename: 'lecture.md', file_type: 'md' }
    upload.mockResolvedValue(lecture)

    const file = new File(['hello world'], 'lecture.md', { type: 'text/markdown' })
    await user.upload(screen.getByLabelText('Choose a document to upload'), file)

    expect(await screen.findByText(/Indexed "lecture.md"/)).toBeInTheDocument()
    expect(screen.getByText('2 documents uploaded')).toBeInTheDocument()
  })

  it('deletes a document after confirmation', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('syllabus.txt')

    await user.click(screen.getByRole('button', { name: 'Delete syllabus.txt' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete' }))

    await waitFor(() => expect(screen.queryByText('syllabus.txt')).not.toBeInTheDocument())
    expect(screen.getByText('No documents uploaded yet.')).toBeInTheDocument()
  })

  it('displays the backend reason when an upload is rejected', async () => {
    // The plan's AdminPage never rendered the store's error, so the Phase 5
    // criterion "Error messages display" went unmet.
    const user = userEvent.setup()
    upload.mockRejectedValue(
      new ApiError('The index was built with local-hash-512', 'EMBEDDING_MISMATCH', 409),
    )
    renderPage()
    await screen.findByText('syllabus.txt')

    await user.upload(
      screen.getByLabelText('Choose a document to upload'),
      new File(['x'], 'lecture.md'),
    )

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The index was built with local-hash-512')
  })

  it('displays a load failure', async () => {
    list.mockRejectedValue(new ApiError('Network Error', 'NETWORK_ERROR', 0))
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Network Error')
  })

  it('warns about an embedding mismatch', async () => {
    stats.mockResolvedValue({ ...STATS, indexed_with: 'local-hash-512' })
    renderPage()
    expect(await screen.findByText(/The index was built with/)).toHaveTextContent('local-hash-512')
  })

  it('refreshes the list on request', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('syllabus.txt')
    list.mockClear()

    await user.click(screen.getByRole('button', { name: 'Refresh' }))

    await waitFor(() => expect(list).toHaveBeenCalled())
  })

  it('rejects an unsupported file without a request', async () => {
    // applyAccept: false, because the input's `accept` attribute would make
    // userEvent drop the file before the component ever sees it.
    const user = userEvent.setup({ applyAccept: false })
    renderPage()
    await screen.findByText('syllabus.txt')
    upload.mockClear()

    await user.upload(
      screen.getByLabelText('Choose a document to upload'),
      new File(['x'], 'slides.pptx'),
    )

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('not a supported file type')
    expect(upload).not.toHaveBeenCalled()
  })

  it('still renders the panel when the status endpoints fail', async () => {
    // The panel exists to show failures; blanking itself because one probe
    // failed hides the thing it was built to surface.
    health.mockRejectedValue(new Error('down'))
    renderPage()

    expect(await screen.findByText('syllabus.txt')).toBeInTheDocument()
    expect(screen.getByText('down')).toBeInTheDocument()
  })
})
