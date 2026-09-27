import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { ModeBadge } from './ModeBadge'

function badgeOrNull(mode: string | null) {
  const { container } = render(<ModeBadge mode={mode} />)
  return container.querySelector('[data-testid="mode-badge"]')
}

function badge(mode: string | null) {
  // Every test using this helper expects a badge to exist; the one test that
  // does not uses badgeOrNull for the null case.
  return badgeOrNull(mode)!
}

describe('ModeBadge', () => {
  it('renders nothing when there is no mode', () => {
    expect(badgeOrNull(null)).toBeNull()
  })

  it('says offline when no model was called', () => {
    const el = badge('offline-extractive')
    expect(el).not.toBeNull()
    expect(el).toHaveTextContent('Offline extractive')
  })

  it('warns that no language model was called in offline mode', () => {
    // The whole point of the badge: an offline answer is retrieved sentences
    // quoted verbatim, and must not look like a generated one.
    expect(badge('offline-extractive')).toHaveAttribute(
      'title',
      expect.stringContaining('No language model was called'),
    )
  })

  it('reports a Groq answer as generated, not offline', () => {
    // Regression: the badge used to treat any mode other than "openai" as
    // offline, so a Groq answer rendered as the amber "no model was called"
    // badge while a model had in fact answered.
    const el = badge('groq')
    expect(el).not.toBeNull()
    expect(el).toHaveTextContent('Generated')
    expect(el).not.toHaveTextContent('Offline')
  })

  it('reports an OpenAI answer as generated', () => {
    expect(badge('openai')).toHaveTextContent('Generated')
  })

  it('treats an unrecognised mode as a real generator', () => {
    // The provider set is open, so a new one must not silently degrade into a
    // claim that nothing was called.
    expect(badge('some-future-provider')).toHaveTextContent('Generated')
  })

  it('names the provider in the tooltip', () => {
    expect(badge('groq')).toHaveAttribute(
      'title',
      expect.stringContaining('groq'),
    )
  })

  it('distinguishes the two states by colour, not only by wording', () => {
    // Colourblind readers and screenshots both rely on this, and "Generated"
    // vs "Offline extractive" is easy to miss in a dense transcript.
    expect(badge('offline-extractive').className).toContain('amber')
    expect(badge('groq').className).toContain('emerald')
  })
})
