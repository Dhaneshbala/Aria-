import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { axe } from 'vitest-axe'

vi.mock('../../services/api', () => ({
  saveConfig: vi.fn(async () => ({ student_name: 'Zed' })),
}))

import Onboarding from '../Onboarding'
import { useStore } from '../../store'

describe('Onboarding (updateConfig crash regression)', () => {
  it('finishes setup without throwing and calls onComplete', async () => {
    useStore.setState(s => ({ config: { ...s.config, student_name: 'Student' } }))
    const onComplete = vi.fn()
    render(<Onboarding onComplete={onComplete} />)
    fireEvent.change(screen.getByPlaceholderText("What's your name?"), {
      target: { value: 'Zed' },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))
    fireEvent.click(screen.getByRole('button', { name: /start learning/i }))
    await screen.findByText(/welcome, zed/i, {}, { timeout: 3000 }).catch(() => null)
    // let the async handler settle
    await new Promise(r => setTimeout(r, 50))
    expect(onComplete).toHaveBeenCalled()
    expect(useStore.getState().config.student_name).toBe('Zed')
  })

  it('has no axe violations on the subjects step', async () => {
    useStore.setState(s => ({ config: { ...s.config, student_name: 'Student' } }))
    const { container } = render(<Onboarding onComplete={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))
    const results = await axe(container)
    expect(results.violations).toEqual([])
  })
})
