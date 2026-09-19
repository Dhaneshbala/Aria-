export default function EmptyState({ icon = '✨', title = 'Nothing here yet', hint = '', action = null }) {
  return (
    <div className="card flex flex-col items-center justify-center px-6 py-10 text-center animate-fade-slide">
      <div className="text-4xl mb-3" aria-hidden="true">{icon}</div>
      <h3 className="text-[15px] font-semibold text-aria-text mb-1">{title}</h3>
      {hint ? <p className="text-[13px] text-aria-muted max-w-sm mb-4">{hint}</p> : null}
      {action}
    </div>
  )
}
