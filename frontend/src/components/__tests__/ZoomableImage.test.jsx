import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ZoomableImage from '../message/ZoomableImage'

describe('ZoomableImage', () => {
  it('lazy-loads and opens fullscreen on tap', () => {
    render(<ZoomableImage src="blob:preview-1" alt="Uploaded image" className="thumb" />)
    const thumb = screen.getByRole('button', { name: /enlarge/i }).querySelector('img')
    expect(thumb).toHaveAttribute('loading', 'lazy')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /enlarge/i }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('dialog'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows a download link only for http(s) urls', () => {
    const { rerender } = render(<ZoomableImage src="blob:preview-1" alt="pic" />)
    expect(screen.queryByText(/download image/i)).not.toBeInTheDocument()
    rerender(<ZoomableImage src="https://example.com/a.png" alt="pic" />)
    expect(screen.getByText(/download image/i)).toBeInTheDocument()
  })
})
