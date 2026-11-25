import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { HealthResponse } from './api/health'

function mockFetch(status: number, body: HealthResponse) {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status }))),
  )
}

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the engine name when the backend is healthy', async () => {
    mockFetch(200, {
      status: 'ok',
      engine: { status: 'ok', name: 'Stockfish 19', detail: null },
    })
    render(<App />)
    expect(await screen.findByText('Motor listo: Stockfish 19')).toBeInTheDocument()
  })

  it('shows the reason when the engine is unavailable', async () => {
    mockFetch(503, {
      status: 'degraded',
      engine: { status: 'unavailable', name: null, detail: 'binary not found' },
    })
    render(<App />)
    expect(await screen.findByText('Motor no disponible: binary not found')).toBeInTheDocument()
  })
})
