import React from 'react'
import { Cpu, Search } from 'lucide-react'

/**
 * The mode value that means no language model was called.
 *
 * Matched by value rather than by "anything that is not openai", because the
 * set of remote providers is open: groq, openai, and whatever endpoint comes
 * next all genuinely call a model. Testing `mode !== 'openai'` made a Groq
 * answer render as the amber offline badge, i.e. the badge asserted the
 * opposite of what happened. An unrecognised mode is therefore assumed to be a
 * real generator, and is named in the tooltip.
 */
const OFFLINE_MODE = 'offline-extractive'

/**
 * Report which generator produced the last answer.
 *
 * This is not decoration. In offline mode no language model was called at
 * all: the answer is retrieved sentences quoted verbatim. Hiding that behind a
 * chat bubble would misrepresent what the system did.
 */
export const ModeBadge: React.FC<{ mode: string | null }> = ({ mode }) => {
  if (!mode) return null

  const offline = mode === OFFLINE_MODE
  const label = offline ? 'Offline extractive' : 'Generated'
  const title = offline
    ? 'No language model was called. The answer quotes the retrieved sentences that best match your question.'
    : `Answered by the ${mode} language model using the retrieved context.`

  return (
    <span
      title={title}
      data-testid="mode-badge"
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
        offline ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'
      }`}
    >
      {offline ? (
        <Search className="h-3 w-3" aria-hidden="true" />
      ) : (
        <Cpu className="h-3 w-3" aria-hidden="true" />
      )}
      {label}
    </span>
  )
}
