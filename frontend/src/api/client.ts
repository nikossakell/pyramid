/**
 * API client (fetch). Base /api/v1, bearer από το auth store, κανονικοποίηση σφαλμάτων.
 * - 401 σε αίτημα με token → onUnauthorized (M09 SessionExpired)
 * - 403 {"study_ended": true} → onStudyEnded (S19), σε ΟΠΟΙΟ αίτημα
 * - 403 {"detail": "not_yet_available"} → onNotYetAvailable (S21)
 * - 429 → ApiError.retryAfter (δευτερόλεπτα από το Retry-After)
 * Δεν γράφει ποτέ στην κονσόλα σώμα αιτήματος, query ή token. Η φωτογραφία πάει ως raw image/jpeg (Blob στη μνήμη).
 */
export const API_BASE = '/api/v1'

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public body: unknown = null,
    public retryAfter: number | null = null,
  ) {
    super(`api ${status} ${detail}`)
  }
}

/** 0 = δεν έγινε σύνδεση (offline, DNS, timeout). */
export const OFFLINE = 0

type Handlers = {
  token: () => string | null
  onUnauthorized: () => void
  onStudyEnded: () => void
  onNotYetAvailable: () => void
}
let handlers: Handlers = { token: () => null, onUnauthorized: () => {}, onStudyEnded: () => {}, onNotYetAvailable: () => {} }
export function installApiHandlers(h: Handlers): void {
  handlers = h
}

export type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  json?: unknown
  blob?: Blob                 // raw σώμα (image/jpeg)
  query?: Record<string, string | undefined>
  auth?: boolean              // προεπιλογή true
  timeoutMs?: number
  signal?: AbortSignal
}

function detailOf(body: unknown): string {
  if (body && typeof body === 'object') {
    const b = body as Record<string, unknown>
    if (b.study_ended === true) return 'study_ended'
    if (b.rejected === true) return 'rejected'
    if (b.photo_unavailable === true) return 'photo_unavailable'
    if (typeof b.detail === 'string') return b.detail
    if (Array.isArray(b.detail)) return 'validation_error'
  }
  return 'error'
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const url = new URL(API_BASE + path, window.location.origin)
  for (const [k, v] of Object.entries(opts.query ?? {})) if (v !== undefined && v !== '') url.searchParams.set(k, v)
  const headers: Record<string, string> = { Accept: 'application/json' }
  const useAuth = opts.auth !== false
  const token = useAuth ? handlers.token() : null
  if (token) headers.Authorization = `Bearer ${token}`
  let body: BodyInit | undefined
  if (opts.blob) {
    headers['Content-Type'] = 'image/jpeg'
    body = opts.blob
  } else if (opts.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.json)
  }
  const controller = new AbortController()
  const timer = opts.timeoutMs ? setTimeout(() => controller.abort(), opts.timeoutMs) : null
  opts.signal?.addEventListener('abort', () => controller.abort())
  let res: Response
  try {
    res = await fetch(url.toString(), { method: opts.method ?? 'GET', headers, body, signal: controller.signal, credentials: 'omit' })
  } catch (e) {
    if (controller.signal.aborted) throw new ApiError(OFFLINE, 'aborted')
    throw new ApiError(OFFLINE, 'offline')
  } finally {
    if (timer) clearTimeout(timer)
  }
  if (res.status === 204) return undefined as T
  const text = await res.text()
  let parsed: unknown = null
  try { parsed = text ? JSON.parse(text) : null } catch { parsed = null }
  if (res.ok) return parsed as T

  const detail = detailOf(parsed)
  const retry = res.headers.get('Retry-After')
  const err = new ApiError(res.status, detail, parsed, retry && /^\d+$/.test(retry) ? Number(retry) : null)
  if (res.status === 401 && useAuth && token) handlers.onUnauthorized()
  if (res.status === 403 && detail === 'study_ended') handlers.onStudyEnded()
  if (res.status === 403 && detail === 'not_yet_available') handlers.onNotYetAvailable()
  throw err
}

export const api = {
  get: <T>(path: string, query?: RequestOptions['query'], opts: RequestOptions = {}) => request<T>(path, { ...opts, query }),
  post: <T>(path: string, json?: unknown, opts: RequestOptions = {}) => request<T>(path, { ...opts, method: 'POST', json }),
  patch: <T>(path: string, json?: unknown, opts: RequestOptions = {}) => request<T>(path, { ...opts, method: 'PATCH', json }),
  delete: <T>(path: string, opts: RequestOptions = {}) => request<T>(path, { ...opts, method: 'DELETE' }),
}
