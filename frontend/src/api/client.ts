export class ApiError extends Error {
  readonly status: number
  /** The backend's `detail`, which may be a structured object (e.g. `{code: ...}`). */
  readonly detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** JSON request to the backend. Errors carry the backend's `detail` message (in Spanish). */
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  const response = await fetch(`/api${path}`, { ...init, headers })
  if (!response.ok) {
    let message = `Error ${String(response.status)}`
    let detail: unknown
    try {
      const body = (await response.json()) as { detail?: unknown }
      detail = body.detail
      if (typeof detail === 'string') message = detail
      else if (isRecord(detail) && typeof detail.message === 'string') message = detail.message
    } catch {
      // Non-JSON error body: keep the generic message.
    }
    throw new ApiError(response.status, message, detail)
  }
  return (await response.json()) as T
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
