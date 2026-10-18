import { http, HttpResponse } from 'msw'

// Default API mocks for tests. Individual tests override via server.use().
// Anything unmocked falls through to the real network (bypass).
export const handlers = [
  http.get('*/api/admin/health', () => HttpResponse.json({
    status: 'ok',
    ollama: true,
    model: 'gemma3:12b',
    embedding_model: 'nomic-embed-text',
  })),
  http.get('*/api/chat/conversations', () => HttpResponse.json([])),
  http.get('*/api/todos', () => HttpResponse.json({ todos: [], cushion: null })),
]
