const _fmt = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

/**
 * Format a UTC ISO timestamp (e.g. "2026-04-08T12:00:00Z") into the
 * browser's local timezone. Returns "—" for null/invalid values.
 */
export function fmtUtc(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  return isNaN(d.getTime()) ? value : _fmt.format(d)
}
