export interface EngineHealth {
  status: 'ok' | 'unavailable'
  name: string | null
  detail: string | null
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  engine: EngineHealth
}

/** GET /health. A 503 still carries a HealthResponse body describing the problem. */
export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch('/api/health', { signal })
  if (response.ok || response.status === 503) {
    return (await response.json()) as HealthResponse
  }
  throw new Error(`HTTP ${String(response.status)}`)
}
