import React from 'react'
import { FileText } from 'lucide-react'
import type { Source } from '../../types'

interface SourceCardProps {
  source: Source
}

export const SourceCard: React.FC<SourceCardProps> = ({ source }) => {
  // Similarity is declared required, but a null must not print as "NaN%".
  const similarity = typeof source.similarity === 'number' ? source.similarity : null

  return (
    <div
      className="flex items-start gap-2 rounded-lg border border-blue-100 bg-blue-50 p-2 text-xs"
      data-testid="source-card"
    >
      <FileText className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-500" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-baseline gap-x-2 font-medium text-blue-900">
          <span className="truncate">{source.filename}</span>
          <span className="text-blue-500">
            chunk {source.chunk_index}
            {similarity !== null && ` · ${(similarity * 100).toFixed(0)}% match`}
          </span>
        </p>
        {source.excerpt && (
          <p className="mt-0.5 line-clamp-2 text-blue-700" title={source.excerpt}>
            {source.excerpt}
          </p>
        )}
      </div>
    </div>
  )
}
