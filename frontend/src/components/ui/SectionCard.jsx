export default function SectionCard({ title, subtitle, action, children }) {
  return (
    <section className="card card-hover p-4 sm:p-5">
      {(title || action) && (
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            {title && <h2 className="text-[15px] font-semibold text-aria-text">{title}</h2>}
            {subtitle && <p className="text-[13px] text-aria-muted mt-0.5">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}
