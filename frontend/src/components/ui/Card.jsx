export function Card({ hover = false, className = '', children, ...props }) {
  return (
    <div className={`card ${hover ? 'card-hover' : ''} ${className}`} {...props}>
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, action, icon }) {
  return (
    <div className="flex items-start justify-between gap-3 mb-3">
      <div className="flex gap-2.5 min-w-0">
        {icon ? <div className="w-8 h-8 rounded-full bg-aria-variant flex items-center justify-center shrink-0">{icon}</div> : null}
        <div className="min-w-0">
          {title && <h3 className="text-[13px] font-semibold tracking-wide uppercase text-aria-muted">{title}</h3>}
          {subtitle && <p className="text-[15px] font-medium text-aria-text mt-0.5 leading-tight">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  )
}

export default Card
