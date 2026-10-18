import { setupServer } from 'msw/node'
import { handlers } from './handlers'

// Shared mock server: reset between tests, closed after the run.
export const server = setupServer(...handlers)
