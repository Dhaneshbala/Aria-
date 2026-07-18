export default function Spinner({ size = 8, text = '' }) {
  return (
    <div className="flex flex-col items-center py-16 gap-3">
      <div className={`w-${size} h-${size} border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin`} />
      {text && <p className="text-[#888] text-sm">{text}</p>}
    </div>
  )
}
