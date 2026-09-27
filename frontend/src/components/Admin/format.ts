/** Display formatting for the admin panel. */

/** Human-readable byte count. Falls back to an em dash if size is unusable. */
export function formatSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * Format an ISO timestamp in the viewer's locale, or report it unusable.
 *
 * A card showing "Invalid Date" is worse than one admitting it does not know
 * the date, so an unparseable value becomes a dash instead of being propagated
 * into the UI.
 */
export function formatDate(iso: string): string {
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return 'unknown date'
  return parsed.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
