import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { EngineStatus } from './EngineStatus'

describe('EngineStatus', () => {
  it('shows nothing when the engine is ready', async () => {
    mockApi([
      {
        path: '/api/health',
        body: { status: 'ok', engine: { status: 'ok', name: 'Stockfish 19', detail: null } },
      },
    ])
    const { container } = render(<EngineStatus />)
    await new Promise((r) => setTimeout(r, 0))
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the reason when the engine is unavailable', async () => {
    mockApi([
      {
        path: '/api/health',
        status: 503,
        body: {
          status: 'degraded',
          engine: { status: 'unavailable', name: null, detail: 'binary not found' },
        },
      },
    ])
    render(<EngineStatus />)
    expect(await screen.findByText('Motor no disponible: binary not found')).toBeInTheDocument()
  })
})
