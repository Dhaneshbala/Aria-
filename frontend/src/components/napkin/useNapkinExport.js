/**
 * useNapkinExport — SVG/PNG/PDF download logic for NapkinDiagram.
 * Extracted from NapkinDiagram.jsx. Blob-URL based (unicode/emoji safe).
 */
import { slugify } from './diagramUtils'

export function svgToImage(svgText) {
  return new Promise((resolve, reject) => {
    const blob = new Blob([svgText], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const img = new Image()
    img.onload = () => { URL.revokeObjectURL(url); resolve(img) }
    img.onerror = (e) => { URL.revokeObjectURL(url); reject(e) }
    img.src = url
  })
}

export function useNapkinExport({ svgRef, title, theme, canvasW, canvasH }) {
  const serialize = () => {
    if (!svgRef.current) return null
    const clone = svgRef.current.cloneNode(true)
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
    return new XMLSerializer().serializeToString(clone)
  }

  const downloadSVG = () => {
    const s = serialize()
    if (!s) return
    const blob = new Blob([s], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${slugify(title)}.svg`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const downloadPNG = async () => {
    const s = serialize()
    if (!s) return
    try {
      const img = await svgToImage(s)
      const canvas = document.createElement('canvas')
      canvas.width = canvasW * 2
      canvas.height = canvasH * 2
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = theme.bg
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.scale(2, 2)
      ctx.drawImage(img, 0, 0, canvasW, canvasH)
      canvas.toBlob((blob) => {
        if (!blob) return
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${slugify(title)}.png`
        a.click()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      })
    } catch (e) { console.warn('PNG export failed:', e) }
  }

  const downloadPDF = async () => {
    const s = serialize()
    if (!s) return
    try {
      const { jsPDF } = await import('jspdf')
      const img = await svgToImage(s)
      const canvas = document.createElement('canvas')
      canvas.width = canvasW * 2
      canvas.height = canvasH * 2
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = theme.bg
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.scale(2, 2)
      ctx.drawImage(img, 0, 0, canvasW, canvasH)
      const pdf = new jsPDF({ unit: 'pt', format: 'a4', orientation: 'landscape' })
      const pw = pdf.internal.pageSize.getWidth()
      pdf.setFontSize(14)
      pdf.text(title, 40, 40)
      pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 40, 55, pw - 80, ((pw - 80) * canvasH) / canvasW)
      pdf.save(`${slugify(title)}.pdf`)
    } catch (e) { console.warn('PDF export failed:', e) }
  }

  return { downloadSVG, downloadPNG, downloadPDF }
}
