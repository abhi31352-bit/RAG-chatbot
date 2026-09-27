import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { LandingPage } from './LandingPage'

function renderPage() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  )
}

describe('LandingPage', () => {
  it('leads with a single top-level heading', () => {
    renderPage()
    expect(
      screen.getByRole('heading', { level: 1, name: /ask your course materials/i }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('explains the premise rather than just naming the product', () => {
    renderPage()
    // A landing page that only says the product name gives a first-time
    // visitor nothing to judge, which is the one job this page has.
    expect(screen.getByText(/retrieval-augmented chatbot/i)).toBeInTheDocument()
  })

  it('shows a feature card per capability', () => {
    renderPage()
    const features = [
      'Upload course materials',
      'Answers grounded in what you uploaded',
      'Says when it does not know',
    ]
    for (const title of features) {
      expect(screen.getByRole('heading', { name: title })).toBeInTheDocument()
    }
  })

  it('claims only behaviour the system has', () => {
    renderPage()
    // Both of these are true, and both are load-bearing in a demo: answers
    // carry citations, and an unanswerable question gets an admission rather
    // than an invention. Asserted so a copy edit cannot quietly remove them.
    expect(screen.getByText(/quotes the passages it used/i)).toBeInTheDocument()
    expect(screen.getByText(/runs with no API key at all/i)).toBeInTheDocument()
  })

  it('walks through the four pipeline stages in order', () => {
    renderPage()
    const section = screen.getByRole('heading', { name: 'How it works' }).closest('section')!
    // Scoped to the section: the feature cards above are also h3s, so an
    // unscoped heading query would pick up seven elements and prove nothing
    // about the order of the four steps.
    const steps = within(section)
      .getAllByRole('heading', { level: 3 })
      .map((el) => el.textContent)
    expect(steps).toEqual(['Upload', 'Index', 'Ask', 'Answer'])
  })

  it('numbers the stages, so the sequence is readable without the prose', () => {
    renderPage()
    const section = screen.getByRole('heading', { name: 'How it works' }).closest('section')!
    for (const n of ['1', '2', '3', '4']) {
      expect(within(section).getByText(n)).toBeInTheDocument()
    }
  })

  it('links onward to both destinations', () => {
    renderPage()
    // Repeated names are intentional, so a bare name matcher would throw on
    // ambiguity rather than quietly picking one link.
    expect(screen.getAllByRole('link', { name: 'Start chatting' })[0]).toHaveAttribute(
      'href',
      '/chat',
    )
    expect(screen.getAllByRole('link', { name: 'Upload documents' })[0]).toHaveAttribute(
      'href',
      '/admin',
    )
    expect(screen.getAllByRole('link', { name: 'Add a document' })[0]).toHaveAttribute(
      'href',
      '/admin',
    )
  })

  it('tells a first-time visitor that an empty index is the normal starting state', () => {
    renderPage()
    const section = screen.getByRole('heading', { name: /nothing indexed yet/i })
    // The single most likely reason a demo looks broken on arrival: asking a
    // question before uploading anything.
    expect(within(section.closest('div')!).getByText(/only knows what has been uploaded/i)).toBeInTheDocument()
  })

  it('renders no navigation of its own', () => {
    // AppRoutes owns the header. A second one here would double it up.
    renderPage()
    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument()
  })
})
