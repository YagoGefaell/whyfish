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
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const path = input
      const raw = init?.body
      calls.push({ method, path, body: typeof raw === 'string' ? JSON.parse(raw) : undefined })
      const route = routes.find((r) => (r.method ?? 'GET') === method && r.path === path)
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
