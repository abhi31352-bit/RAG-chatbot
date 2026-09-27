import React, { useState } from 'react'
import { FileText, Trash2, Loader2, Clock } from 'lucide-react'
import { ConfirmDialog } from './ConfirmDialog'
import { formatDate, formatSize } from './format'
import type { Document } from '../../types'

interface DocumentCardProps {
  document: Document
  onDelete: (id: string) => Promise<boolean> | void
  isDeleting?: boolean
}

const FILE_TYPE_COLORS: Record<string, string> = {
  pdf: 'bg-red-100 text-red-700',
  docx: 'bg-blue-100 text-blue-700',
  txt: 'bg-gray-100 text-gray-700',
  md: 'bg-purple-100 text-purple-700',
}

const STATUS_STYLES: Record<string, string> = {
  processed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  pending: 'bg-yellow-100 text-yellow-700',
}

const STATUS_LABELS: Record<string, string> = {
  processed: 'indexed',
  failed: 'failed',
  pending: 'processing',
}

export const DocumentCard: React.FC<DocumentCardProps> = ({ document, onDelete, isDeleting = false }) => {
  const [isConfirming, setIsConfirming] = useState(false)

  const color = FILE_TYPE_COLORS[document.file_type] ?? 'bg-gray-100 text-gray-700'
  const statusStyle = STATUS_STYLES[document.status] ?? 'bg-gray-100 text-gray-600'
  const statusLabel = STATUS_LABELS[document.status] ?? document.status

  const confirmDelete = async () => {
    const result = await onDelete(document.id)
    // Only close on success, so a rejected delete leaves the dialog open with
    // the reason visible instead of appearing to have worked.
    if (result !== false) setIsConfirming(false)
  }

  return (
    <>
      <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3 transition-shadow hover:shadow-sm">
        <div
          className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg ${color}`}
          aria-hidden="true"
        >
          <FileText className="h-4 w-4" />
        </div>

        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-gray-900">{document.filename}</p>
          <div className="mt-0.5 flex flex-wrap items-center gap-3 text-xs text-gray-500">
            <span>{document.chunk_count} chunks</span>
            <span>{formatSize(document.file_size)}</span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" aria-hidden="true" />
              {formatDate(document.created_at)}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusStyle}`}>
              {statusLabel}
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsConfirming(true)}
          disabled={isDeleting}
          aria-label={`Delete ${document.filename}`}
          className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500 disabled:opacity-50"
        >
          {isDeleting ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </div>

      <ConfirmDialog
        open={isConfirming}
        title="Delete this document?"
        message={`"${document.filename}" and its ${document.chunk_count} indexed ${
          document.chunk_count === 1 ? 'chunk' : 'chunks'
        } will be removed. The chatbot will stop citing it.`}
        confirmLabel="Delete"
        isBusy={isDeleting}
        onConfirm={confirmDelete}
        onCancel={() => setIsConfirming(false)}
      />
    </>
  )
}
