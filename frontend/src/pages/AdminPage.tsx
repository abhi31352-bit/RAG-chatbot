import React from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import { UploadButton } from '../components/Admin/UploadButton'
import { DocumentList } from '../components/Admin/DocumentList'
import { SystemStatus } from '../components/Admin/SystemStatus'
import { useDocuments } from '../hooks/useDocuments'
import { useSystemStatus } from '../hooks/useSystemStatus'

export const AdminPage: React.FC = () => {
  const {
    documents,
    isLoading,
    isUploading,
    uploadProgress,
    uploadPhase,
    deletingId,
    notice,
    error,
    refresh,
    upload,
    remove,
  } = useDocuments()
  const { health, readiness, stats, isLoading: isStatusLoading, error: statusError, refresh: refreshStatus } =
    useSystemStatus()

  return (
    <div className="h-full overflow-y-auto bg-gray-50">
      <header className="border-b bg-white">
        <div className="mx-auto max-w-4xl px-4 py-4">
          <h1 className="text-xl font-semibold text-gray-900">Document management</h1>
          <p className="text-sm text-gray-500">Upload and manage the material the chatbot can cite</p>
        </div>
      </header>

      <main className="mx-auto max-w-4xl space-y-8 px-4 py-6">
        <section>
          <h2 className="mb-3 text-sm font-medium text-gray-700">Upload documents</h2>
          <UploadButton
            isUploading={isUploading}
            uploadProgress={uploadProgress}
            uploadPhase={uploadPhase}
            onUpload={(file) => void upload(file)}
          />
          {notice && (
            <p role="status" className="mt-2 text-sm text-green-700">
              {notice}
            </p>
          )}
          {error && (
            <p role="alert" className="mt-2 text-sm text-red-600">
              {error}
            </p>
          )}
        </section>

        <SystemStatus
          health={health}
          readiness={readiness}
          stats={stats}
          isLoading={isStatusLoading}
          error={statusError}
          onRefresh={() => void refreshStatus()}
        />

        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-gray-700">Uploaded documents</h2>
            <button
              type="button"
              onClick={() => void refresh()}
              disabled={isLoading}
              className="flex items-center gap-1.5 text-sm text-gray-500 transition-colors hover:text-gray-700 disabled:opacity-50"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
              )}
              Refresh
            </button>
          </div>

          {isLoading && documents.length === 0 ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" aria-hidden="true" />
            </div>
          ) : (
            <DocumentList documents={documents} onDelete={remove} deletingId={deletingId} />
          )}
        </section>
      </main>
    </div>
  )
}
