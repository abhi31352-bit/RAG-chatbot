/**
 * Client-side pre-flight checks for an upload.
 *
 * These duplicate rules the backend already enforces. That is deliberate, and
 * only a courtesy: the backend re-checks the extension and the size itself and
 * its answer is what ends up in the error banner, so nothing here is a
 * security boundary. What the client adds is that an unusable file fails
 * immediately instead of after a full round trip -- most visibly for the empty
 * file, where the server would answer `EMPTY_FILE` having already received a
 * 0-byte body.
 */

/** Mirrors `ALLOWED_EXTENSIONS` in backend/app/utils/file_handler.py. */
export const ACCEPTED_EXTENSIONS = ['pdf', 'txt', 'docx', 'md'] as const

export const ACCEPT_ATTRIBUTE = ACCEPTED_EXTENSIONS.map((ext) => `.${ext}`).join(',')

/** Mirrors `MAX_FILE_SIZE_MB` in backend/app/config.py. */
export const MAX_FILE_SIZE_MB = 50

function extensionOf(filename: string): string {
  const dot = filename.lastIndexOf('.')
  return dot === -1 ? '' : filename.slice(dot + 1).toLowerCase()
}

/** Return a human-readable reason the file cannot be uploaded, or null. */
export function validateFile(file: File): string | null {
  const ext = extensionOf(file.name)
  if (!ACCEPTED_EXTENSIONS.includes(ext as (typeof ACCEPTED_EXTENSIONS)[number])) {
    return `"${file.name}" is not a supported file type. Allowed types: PDF, TXT, DOCX, MD.`
  }
  if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
    return `"${file.name}" is larger than the ${MAX_FILE_SIZE_MB}MB limit.`
  }
  if (file.size === 0) {
    return `"${file.name}" is empty, so there is nothing to index.`
  }
  return null
}
