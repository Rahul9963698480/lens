/** Coerce API error bodies (FastAPI-style) into a user-facing string. */
export function apiErrorMessage(
  data: unknown,
  fallback = 'An error occurred',
): string {
  if (data == null) return fallback;
  if (typeof data === 'string') {
    const t = data.trim();
    return t || fallback;
  }
  if (typeof data !== 'object') return fallback;
  const record = data as Record<string, unknown>;
  if (typeof record.message === 'string' && record.message.trim()) {
    return record.message.trim();
  }
  if (typeof record.detail === 'string' && record.detail.trim()) {
    return record.detail.trim();
  }
  if (typeof record.error === 'string' && record.error.trim()) {
    return record.error.trim();
  }
  return fallback;
}
