export default function Spinner({ size = 8, text = '' }) {
  return (
    <div className="flex flex-col items-center py-16 gap-3">
      <div
        className="border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin"
        style={{ width: `${size * 4}px`, height: `${size * 4}px` }}
      />
      {text && <p className="text-[#888] text-sm">{text}</p>}
    </div>
  )
}
