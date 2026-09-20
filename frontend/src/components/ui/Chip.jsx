export function Chip({ active, children, className = '', ...props }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs border transition-colors ${active ? 'bg-aria-accent/15 text-aria-accent-light border-aria-accent/30' : 'bg-aria-surface text-aria-muted border-aria-border hover:text-aria-text hover:border-aria-border-light'} ${className}`} {...props}>
      {children}
    </span>
  )
}

export function ModeChip({ children }) {
  return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-aria-accent/15 border border-aria-accent/20 text-xs text-aria-accent-light font-medium">{children}</span>
}

export default Chip
