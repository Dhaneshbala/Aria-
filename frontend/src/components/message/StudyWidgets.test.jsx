import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ToolResult } from './StudyWidgets'

// Regression: StudyWidgets used isSafeUrl without importing it (lost in the
// "extracted from Message.jsx" refactor). It built fine and crashed at render
// with "Can't find variable: isSafeUrl" the first time a chat returned web
// results. Rendering a web_search tool result pins the import.
describe('ToolResult web_search', () => {
  it('renders result links without crashing', () => {
    const tool = {
      tool: 'web_search',
      content: [
        { title: 'Example', url: 'https://example.com', snippet: 'hi' },
        { title: 'Bad', url: 'javascript:alert(1)', snippet: 'x' },
      ],
    }
    const { container } = render(<ToolResult tool={tool} />)
    expect(screen.getByText('Example').closest('a')).toHaveAttribute('href', 'https://example.com')
    // unsafe URL renders as plain text, never a link
    expect(screen.getByText('Bad').tagName).toBe('SPAN')
    expect(container.querySelector('a[href^="javascript:"]')).toBeNull()
  })
})
