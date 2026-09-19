import { describe, it, expect, vi, afterEach } from 'vitest'
import { ApiError, parseSseStream } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('ApiError', () => {
  it('carries status, type, message, hint', () => {
    const e = new ApiError(429, 'rate_limited', 'Slow down', 'Wait a bit')
    expect(e.status).toBe(429)
    expect(e.type).toBe('rate_limited')
    expect(e.hint).toBe('Wait a bit')
  })
})

describe('parseSseStream', () => {
  it('parses data: lines and returns done payload', async () => {
    const enc = new TextEncoder()
    const chunks = [
      'data: {"type":"token","content":"hi"}\n',
      'data: {"type":"done"}\n',
    ]
    const stream = new ReadableStream({
      start(c) {
        for (const ch of chunks) c.enqueue(enc.encode(ch))
        c.close()
      },
    })
    const seen = []
    const done = await parseSseStream({ body: stream }, (d) => seen.push(d.type))
    expect(seen).toEqual(['token', 'done'])
    expect(done?.type).toBe('done')
  })
})
