import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Render assistant text as markdown.
 *
 * Shared by finished messages and the in-flight stream so the typography does
 * not visibly jump the moment an answer completes.
 */
export const MarkdownContent: React.FC<{ children: string }> = ({ children }) => (
  <div className="prose prose-sm max-w-none prose-headings:font-semibold prose-pre:bg-gray-50">
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
  </div>
)
