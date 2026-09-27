import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes } from './App'
import { chatService } from './services/chatService'
import { documentService } from './services/documentService'
import { systemService } from './services/systemService'

/**
 * Routing is tested against the real pages, not stubs.
 *
 * A stubbed page would prove only that `<Route>` was wired to *something*.
 * The things that actually break in a router change are subtler: a page
 * mounted outside the router context, a redirect that sends a refresh to the
 * wrong place, a header that disappears on one route. Those need the real
 * trees, so the three service modules are mocked instead and the pages mount
 * for real.
 */
vi.mock('./services/chatService', () => ({
  chatService: {
    streamQuery: vi.fn(),
    clearSession: vi.fn(),
    getHistory: vi.fn(),
  },
}))

vi.mock('./services/documentService', () => ({
  documentService: {
    list: vi.fn(),
    upload: vi.fn(),
    remove: vi.fn(),
    stats: vi.fn(),
  },
}))

vi.mock('./services/systemService', () => ({
  systemService: {
    health: vi.fn(),
    ready: vi.fn(),
  },
}))

const getHistory = vi.mocked(chatService.getHistory)
const list = vi.mocked(documentService.list)
const stats = vi.mocked(documentService.stats)
const health = vi.mocked(systemService.health)
const ready = vi.mocked(systemService.ready)

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )
}

/** The landing page's only h1, so these assertions are not satisfied by the nav. */
const HERO = 'Ask your course materials anything'

/**
 * Wait for the admin page's three mount-time fetches to land.
 *
 * Routing assertions are about the router, but the admin page fetches on mount,
 * so a synchronous test finishes while those promises are still pending. That
 * produces `act()` warnings and, worse, leaves updates queued into the next
 * test after cleanup. The empty-state text only appears once `list()` has
 * resolved, so finding it is a real settle signal.
 */
function adminSettled() {
  return screen.findByText('No documents uploaded yet.')
}

beforeEach(() => {
  getHistory.mockReset().mockResolvedValue([])
  // The wrapper object, not a bare array: `list()` decodes
  // `{documents, total}` and the hook hands `response.documents` straight to
  // the list, so a bare `[]` here silently feeds it `undefined`.
  list.mockReset().mockResolvedValue({ documents: [], total: 0 })
  stats.mockReset().mockResolvedValue({
    collection_name: 'documents',
    total_chunks: 0,
    embedding_provider: 'local',
    embedding_model: 'local-hash-2048',
    indexed_with: 'local-hash-2048',
  })
  health.mockReset().mockResolvedValue({
    status: 'healthy',
    app_name: 'RAG Chatbot',
    environment: 'test',
    llm_model: 'test-model',
  })
  ready.mockReset().mockResolvedValue({ ready: true, checks: { database: true } })
})

describe('AppRoutes', () => {
  describe('each route renders its own page', () => {
    it('serves the landing page at the root', () => {
      renderAt('/')
      expect(screen.getByRole('heading', { level: 1, name: HERO })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'How it works' })).toBeInTheDocument()
    })

    it('serves the chat page at /chat', () => {
      renderAt('/chat')
      expect(screen.queryByRole('heading', { level: 1, name: HERO })).not.toBeInTheDocument()
      // The suggested questions only exist on an empty chat, which is the
      // cheapest reliable signal that the chat mounted rather than the landing.
      expect(screen.getByRole('button', { name: /who is the ta/i })).toBeInTheDocument()
    })

    it('serves the admin page at /admin', async () => {
      renderAt('/admin')
      expect(screen.getByRole('heading', { name: 'Document management' })).toBeInTheDocument()
      await adminSettled()
    })
  })

  describe('unknown routes', () => {
    it('redirects to the landing page rather than a blank screen', () => {
      // A presenter who mistypes a URL, or follows a stale bookmark, should
      // land somewhere useful instead of an empty shell.
      renderAt('/does-not-exist')
      expect(screen.getByRole('heading', { level: 1, name: HERO })).toBeInTheDocument()
    })

    it('redirects a deep unknown path too', () => {
      renderAt('/chat/nonsense/more')
      expect(screen.getByRole('heading', { level: 1, name: HERO })).toBeInTheDocument()
    })
  })

  describe('header', () => {
    it('appears exactly once on every page', async () => {
      // The plan's LandingPage snippet renders its own Header while App also
      // renders one. Two nav bars on the landing page is the bug this catches.
      for (const path of ['/', '/chat', '/admin']) {
        const { unmount } = renderAt(path)
        expect(screen.getAllByRole('navigation', { name: 'Primary' })).toHaveLength(1)
        if (path === '/admin') await adminSettled()
        unmount()
      }
    })

    it('keeps the header mounted while navigating between pages', async () => {
      const user = userEvent.setup()
      renderAt('/')
      const nav = screen.getByRole('navigation', { name: 'Primary' })
      // A remount would replace this node; holding the reference and asserting
      // it is still in the document is how a scroll-jumping header shows up.
      expect(nav).toBeInTheDocument()
      expect(screen.getAllByRole('navigation', { name: 'Primary' })[0]).toBe(nav)

      await user.click(screen.getByRole('link', { name: /^Documents$/ }))
      await adminSettled()
      expect(screen.getAllByRole('navigation', { name: 'Primary' })[0]).toBe(nav)
    })
  })

  describe('navigation', () => {
    it('moves from the landing page to the chat page', async () => {
      const user = userEvent.setup()
      renderAt('/')

      await user.click(screen.getByRole('link', { name: 'Start chatting' }))

      expect(screen.queryByRole('heading', { level: 1, name: HERO })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: /who is the ta/i })).toBeInTheDocument()
    })

    it('moves from the landing page to the admin page', async () => {
      const user = userEvent.setup()
      renderAt('/')

      await user.click(screen.getByRole('link', { name: 'Add a document' }))

      expect(screen.getByRole('heading', { name: 'Document management' })).toBeInTheDocument()
      await adminSettled()
    })

    it('moves between pages using the header alone', async () => {
      const user = userEvent.setup()
      renderAt('/chat')

      await user.click(screen.getByRole('link', { name: /^Documents$/ }))
      expect(screen.getByRole('heading', { name: 'Document management' })).toBeInTheDocument()
      await adminSettled()

      await user.click(screen.getByRole('link', { name: /^Home$/ }))
      expect(screen.getByRole('heading', { level: 1, name: HERO })).toBeInTheDocument()

      await user.click(screen.getByRole('link', { name: /^Chat$/ }))
      expect(screen.getByRole('button', { name: /who is the ta/i })).toBeInTheDocument()
    })

    it('highlights the destination after navigating, not just on a fresh load', async () => {
      // `aria-current` is derived from useLocation, so it has to update in
      // response to a click. A stale highlight looks like a broken link.
      const user = userEvent.setup()
      renderAt('/')

      expect(screen.getByRole('link', { name: /^Home$/ })).toHaveAttribute('aria-current', 'page')

      await user.click(screen.getByRole('link', { name: /^Documents$/ }))

      expect(screen.getByRole('link', { name: /^Documents$/ })).toHaveAttribute(
        'aria-current',
        'page',
      )
      expect(screen.getByRole('link', { name: /^Home$/ })).not.toHaveAttribute('aria-current')
    })
  })
})
