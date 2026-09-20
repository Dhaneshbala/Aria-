import { forwardRef } from 'react'

const base = 'inline-flex items-center justify-center gap-1.5 font-medium transition-all touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-aria-accent/40 disabled:opacity-40 disabled:pointer-events-none select-none'

const variants = {
  primary: 'btn-primary shadow-card hover:shadow-card-hover active:translate-y-0',
  ghost: 'bg-aria-surface border border-aria-border text-aria-text hover:bg-aria-variant hover:border-aria-border-light',
  chip: 'bg-aria-surface border border-aria-border text-aria-muted hover:text-aria-text hover:bg-aria-variant text-xs',
  subtle: 'text-aria-muted hover:text-aria-text hover:bg-aria-variant',
}

const sizes = {
  sm: 'px-3 py-1.5 text-xs rounded-full',
  md: 'px-4 py-2 text-sm rounded-pill',
  lg: 'px-5 py-2.5 text-sm rounded-pill',
  icon: 'p-2 rounded-full',
}

export const Button = forwardRef(function Button({ variant = 'primary', size = 'md', className = '', children, ...props }, ref) {
  return (
    <button ref={ref} className={`${base} ${variants[variant] || variants.primary} ${sizes[size] || sizes.md} ${className}`} {...props}>
      {children}
    </button>
  )
})

export default Button
