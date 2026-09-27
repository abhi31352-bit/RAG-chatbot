import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Header } from './Header'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Header />
      <Routes>
        <Route path="*" element={<div>page body</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Header', () => {
  it('links to all three destinations', () => {
    renderAt('/chat')
    // Anchored matchers: the brand link's accessible name is "RAG Chatbot",
    // which a bare /Chat/ also matches.
    expect(screen.getByRole('link', { name: /^Home$/ })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: /^Chat$/ })).toHaveAttribute('href', '/chat')
    expect(screen.getByRole('link', { name: /^Documents$/ })).toHaveAttribute('href', '/admin')
  })

  it('marks the current page for assistive tech and styling', () => {
    renderAt('/admin')
    expect(screen.getByRole('link', { name: /^Documents$/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: /^Chat$/ })).not.toHaveAttribute('aria-current')
    expect(screen.getByRole('link', { name: /^Home$/ })).not.toHaveAttribute('aria-current')
  })

  it('marks the landing page as current only at the root', () => {
    // "/" and "/chat" are the most likely pair to get confused: an exact
    // comparison is the only thing that keeps Home from lighting up everywhere.
    renderAt('/')
    expect(screen.getByRole('link', { name: /^Home$/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: /^Chat$/ })).not.toHaveAttribute('aria-current')
  })

  it('sends the wordmark home rather than to the chat', () => {
    renderAt('/chat')
    expect(screen.getByRole('link', { name: 'RAG Chatbot' })).toHaveAttribute('href', '/')
  })

  it('offers a way into the admin panel', () => {
    // The Phase 5 plan never says how a user reaches /admin, which it defers
    // to the routing task in Phase 6.
    renderAt('/chat')
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument()
  })
})
