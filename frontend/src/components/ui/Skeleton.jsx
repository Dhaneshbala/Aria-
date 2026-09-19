export function SkeletonLine({ w = '100%', h = 14 }) {
  return <div className="skeleton" style={{ width: w, height: h }} aria-hidden="true" />
}

export default function Skeleton({ lines = 3 }) {
  return (
    <div className="flex flex-col gap-2 p-4" role="status" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonLine key={i} w={`${100 - i * 12}%`} />
      ))}
    </div>
  )
}
