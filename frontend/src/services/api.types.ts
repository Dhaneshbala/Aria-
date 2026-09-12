// Central API types — single source of truth for frontend/backend contract
// Backend schemas: backend/routers/study.py, backend/routers/v2.py

export type QuizQuestion = {
  question: string
  options: string[] // exactly 4, A) B) C) D)
  correct: string // 'A'|'B'|'C'|'D' or '' when not verified
  explanation: string
  verified: 'triple_verified' | 'majority_verified' | 'disputed' | 'original' | 'no_data'
}

export type QuizResponse = {
  questions: QuizQuestion[]
  mode?: string | null
}

export type FlashcardsResponse = {
  cards: { front: string; back: string }[]
}

export type ApiError = {
  detail: string | { message: string; hint?: string }
}

export type SrCard = {
  id: string
  front: string
  back: string
  subject: string
  ease_factor: number
  interval: number
  repetitions: number
  next_review: string
}

export type WeakTopic = {
  topic: string
  accuracy: number
  attempts: number
}
