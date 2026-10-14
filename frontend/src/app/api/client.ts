const BASE = '/api'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

// Full URL paths (BASE + path) that may return 401 without triggering a logout
// redirect. /api/me is the router-guard probe — a 401 means "not logged in
// yet". /api/auth/login is the login endpoint itself.
const SILENT_401_PATHS = new Set(['/api/me', '/api/auth/login'])

// Called by the auth store so the client can clear state before redirecting.
let onSessionExpired: (() => void) | null = null
export function setSessionExpiredHandler(fn: () => void) {
  onSessionExpired = fn
}

async function request<T>(path: string, init: RequestInit = {}, isForm = false): Promise<T> {
  const headers: Record<string, string> = isForm ? {} : { 'Content-Type': 'application/json' }
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: 'include',
    headers: { ...headers, ...((init.headers as Record<string, string>) ?? {}) },
  })

  if (!res.ok) {
    // Session expired — clear store state and send to login.
    // Skip for auth-check paths where 401 is a normal "not logged in" response.
    if (res.status === 401 && !SILENT_401_PATHS.has(`${BASE}${path}`) && window.location.pathname !== '/login') {
      if (onSessionExpired) onSessionExpired()
      else window.location.href = '/login'
      throw new ApiError(401, 'Session expired')
    }

    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail)
  }

  // 204 No Content
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: 'POST', body: form }, true),
}
