import React, { useCallback, useRef, useState } from 'react'
import { Loader2, FileText, AlertCircle } from 'lucide-react'
import { ACCEPT_ATTRIBUTE, MAX_FILE_SIZE_MB, validateFile } from './validateFile'

export interface UploadButtonProps {
  isUploading: boolean
  uploadProgress: number
  /** 'indexing' means the bytes are sent and the server is embedding. */
  uploadPhase: 'idle' | 'uploading' | 'indexing'
  onUpload: (file: File) => void
  disabled?: boolean
}

export const UploadButton: React.FC<UploadButtonProps> = ({
  isUploading,
  uploadProgress,
  uploadPhase,
  onUpload,
  disabled = false,
}) => {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const blocked = disabled || isUploading

  const handleFile = useCallback(
    (file: File) => {
      const problem = validateFile(file)
      if (problem) {
        setLocalError(problem)
        return
      }
      setLocalError(null)
      onUpload(file)
    },
    [onUpload],
  )

  const onInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    // Clear the value so re-picking the same file fires `change` again --
    // otherwise a failed upload retried with the identical file does nothing.
    event.target.value = ''
    if (file) handleFile(file)
  }

  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    if (blocked) return
    const file = event.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault()
          if (!blocked) setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        className={`rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors ${
          isDragging
            ? 'border-blue-400 bg-blue-50'
            : blocked
              ? 'border-gray-200 bg-gray-50 opacity-60'
              : 'border-gray-300 bg-white hover:border-blue-300'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT_ATTRIBUTE}
          onChange={onInputChange}
          disabled={blocked}
          aria-label="Choose a document to upload"
          className="sr-only"
        />

        {isUploading ? (
          <div className="mx-auto max-w-sm">
            <div className="flex items-center justify-center gap-2 text-sm font-medium text-gray-700">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              {uploadPhase === 'indexing' ? 'Indexing document…' : 'Uploading…'}
            </div>
            <div
              role="progressbar"
              aria-valuenow={uploadProgress}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Upload progress"
              className="mt-3 h-2 w-full overflow-hidden rounded-full bg-gray-200"
            >
              <div
                className={`h-full rounded-full transition-all ${
                  uploadPhase === 'indexing' ? 'bg-emerald-500' : 'bg-blue-600'
                }`}
                style={{ width: `${Math.min(100, uploadProgress)}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-gray-500">
              {uploadPhase === 'indexing'
                ? 'Bytes received — the server is splitting and embedding the text.'
                : `${uploadProgress}%`}
            </p>
          </div>
        ) : (
          <>
            <FileText className="mx-auto h-8 w-8 text-gray-400" aria-hidden="true" />
            <p className="mt-2 text-sm text-gray-600">
              Drop a file here, or{' '}
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="font-medium text-blue-600 underline underline-offset-2 hover:text-blue-700"
              >
                browse
              </button>
            </p>
            <p className="mt-1 text-xs text-gray-400">PDF, TXT, DOCX or MD · up to {MAX_FILE_SIZE_MB}MB</p>
          </>
        )}
      </div>

      {localError && (
        <p role="alert" className="mt-2 flex items-start gap-1.5 text-xs text-red-600">
          <AlertCircle className="mt-px h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
          {localError}
        </p>
      )}
    </div>
  )
}
