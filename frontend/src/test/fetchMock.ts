import { vi } from 'vitest'

type Route = { method?: string; path: string; status?: number; body: unknown }

export interface FetchCall {
  method: string
  path: string
  body: unknown
}

/** Stub global fetch with fixed responses per (method, path). Returns the recorded calls. */
export function mockApi(routes: Route[]): FetchCall[] {
  const calls: FetchCall[] = []
  const counts = new Map<string, number>()
  const used = (method: string, path: string) => {
    const key = `${method} ${path}`
    const n = counts.get(key) ?? 0
    counts.set(key, n + 1)
    return n
  }
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const path = input
      const raw = init?.body
      calls.push({ method, path, body: typeof raw === 'string' ? JSON.parse(raw) : undefined })
      // Several routes for the same request are used in order; the last one repeats.
      const matching = routes.filter((r) => (r.method ?? 'GET') === method && r.path === path)
      const route =
        matching.length > 1 ? (matching.at(used(method, path)) ?? matching.at(-1)) : matching.at(0)
      if (!route) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: 'not mocked' }), { status: 404 }),
        )
      }
      return Promise.resolve(
        new Response(JSON.stringify(route.body), { status: route.status ?? 200 }),
      )
    }),
  )
  return calls
}
