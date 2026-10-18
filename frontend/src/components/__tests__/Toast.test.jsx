import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { showToast, ToastContainer } from '../Toast'

beforeEach(() => {
  vi.useFakeTimers()
})

describe('Toast actions', () => {
  it('renders an action button that fires and dismisses', async () => {
    const onClick = vi.fn()
    render(<ToastContainer />)
    await act(async () => {
      showToast('Load failed', 'error', 5000, { label: 'Retry', onClick })
    })
    const btn = screen.getByRole('button', { name: 'Retry' })
    expect(btn).toBeInTheDocument()
    await act(async () => {
      fireEvent.click(btn)
    })
    expect(onClick).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('Load failed')).not.toBeInTheDocument()
  })

  it('auto-dismisses after duration', async () => {
    render(<ToastContainer />)
    await act(async () => {
      showToast('Brief', 'success', 1000)
    })
    expect(screen.getByText('Brief')).toBeInTheDocument()
    await act(async () => {
      vi.advanceTimersByTime(1500)
    })
    expect(screen.queryByText('Brief')).not.toBeInTheDocument()
  })
})
