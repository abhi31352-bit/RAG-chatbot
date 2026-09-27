import React from 'react'
import { FileQuestion } from 'lucide-react'
import { DocumentCard } from './DocumentCard'
import type { Document } from '../../types'

interface DocumentListProps {
  documents: Document[]
  onDelete: (id: string) => Promise<boolean> | void
  deletingId?: string | null
}

export const DocumentList: React.FC<DocumentListProps> = ({ documents, onDelete, deletingId = null }) => {
  if (documents.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-white py-12 text-center">
        <FileQuestion className="mx-auto h-7 w-7 text-gray-300" aria-hidden="true" />
        <p className="mt-2 text-sm text-gray-500">No documents uploaded yet.</p>
        <p className="mt-1 text-xs text-gray-400">
          Upload a PDF, TXT, DOCX or MD above to get started.
        </p>
      </div>
    )
  }

  return (
    <div>
      <p className="mb-3 text-sm text-gray-500">
        {documents.length} document{documents.length !== 1 ? 's' : ''} uploaded
      </p>
      <ul className="space-y-2">
        {documents.map((doc) => (
          <li key={doc.id}>
            <DocumentCard
              document={doc}
              onDelete={onDelete}
              isDeleting={deletingId === doc.id}
            />
          </li>
        ))}
      </ul>
    </div>
  )
}
