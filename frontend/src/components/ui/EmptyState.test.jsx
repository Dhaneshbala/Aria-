import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import EmptyState from './EmptyState'

describe('EmptyState', () => {
  it('renders title and hint', () => {
    render(<EmptyState title="No chats yet" hint="Start a conversation" />)
    expect(screen.getByText('No chats yet')).toBeInTheDocument()
    expect(screen.getByText('Start a conversation')).toBeInTheDocument()
  })
})
