import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/mocks/server'
import { getHealth, getConversations } from '../api'

describe('api with MSW', () => {
  it('reads the mocked health endpoint', async () => {
    const h = await getHealth()
    expect(h.ollama).toBe(true)
    expect(h.model).toBe('gemma3:12b')
  })

  it('supports per-test overrides', async () => {
    server.use(
      http.get('*/api/chat/conversations', () => HttpResponse.json([
        { id: 'c1', title: 'Fractions' },
      ])),
    )
    const convos = await getConversations()
    expect(convos).toHaveLength(1)
    expect(convos[0].title).toBe('Fractions')
  })
})
