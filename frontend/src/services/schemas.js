import { z } from 'zod'

// Runtime contracts for backend responses. Fail-open: on mismatch we warn
// and return the raw payload (backend evolves faster than the UI).

const conversationSchema = z.object({
  id: z.string(),
  title: z.string().catch('Untitled'),
  timestamp: z.string().optional(),
  last_timestamp: z.string().optional(),
  turn_count: z.number().optional(),
}).passthrough()

const healthSchema = z.object({
  status: z.string().optional(),
  ollama: z.boolean().optional(),
}).passthrough()

const todoSchema = z.object({
  id: z.string(),
  task: z.string(),
  subject: z.string().optional(),
  completed: z.boolean().optional(),
}).passthrough()

export function validate(schema, data, label) {
  const parsed = schema.safeParse(data)
  if (!parsed.success) {
    console.warn(`[api] unexpected ${label} shape`, parsed.error.issues?.slice(0, 3))
    return data
  }
  return parsed.data
}

export const Schemas = { conversationSchema, healthSchema, todoSchema }
