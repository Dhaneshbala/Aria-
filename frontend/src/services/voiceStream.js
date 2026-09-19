// Day 2: WebSocket streaming STT client with REST fallback.
// Protocol (backend/routers/voice.py ws_transcribe):
//   → binary audio chunks (MediaRecorder timeslices)
//   → JSON {type:'config'|'flush'|'reset'}
//   ← JSON {type:'ready'|'vad'|'partial'|'final'|'reset'|'error'}
//
// Usage:
//   const s = new VoiceStream({ onVad, onPartial, onFinal, onError })
//   await s.connect() // throws on failure → caller falls back to REST
//   s.sendAudio(blob); s.flush(); s.reset(); s.close()

function wsUrl(path) {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${path}`
}

export class VoiceStream {
  constructor({ onVad, onPartial, onFinal, onError, language } = {}) {
    this.onVad = onVad
    this.onPartial = onPartial
    this.onFinal = onFinal
    this.onError = onError
    this.language = language || (typeof navigator !== 'undefined' ? navigator.language : null)
    this.ws = null
    this.connected = false
    this._finalResolvers = []
  }

  connect(url) {
    return new Promise((resolve, reject) => {
      let settled = false
      const done = (fn, val) => { if (!settled) { settled = true; fn(val) } }
      try {
        this.ws = new WebSocket(url || wsUrl('/api/voice/ws-transcribe'))
      } catch (e) {
        done(reject, e)
        return
      }
      const to = setTimeout(() => {
        try { this.ws?.close() } catch {}
        done(reject, new Error('Voice stream connect timeout'))
      }, 8000)
      this.ws.binaryType = 'arraybuffer'
      this.ws.onopen = () => {
        this.connected = true
        try {
          this.ws.send(JSON.stringify({ type: 'config', language: this.language, mime: 'audio/webm' }))
        } catch {}
      }
      this.ws.onmessage = (ev) => {
        let msg = null
        try { msg = JSON.parse(ev.data) } catch { return }
        if (!msg || !msg.type) return
        if (msg.type === 'ready' && !settled) {
          clearTimeout(to)
          done(resolve, msg)
        } else if (msg.type === 'vad') {
          this.onVad?.(msg)
        } else if (msg.type === 'partial') {
          this.onPartial?.(msg.text || '', msg)
        } else if (msg.type === 'final') {
          const text = msg.transcript || msg.text || ''
          this._finalResolvers.splice(0).forEach((r) => r(text))
          this.onFinal?.(text, msg)
        } else if (msg.type === 'error') {
          const err = new Error(msg.message || msg.code || 'stream error')
          this.onError?.(err, msg)
          // Day 44: server is at capacity (max 4 streams) — fail the connect
          // now with a clear message so callers fall back to REST at once.
          if (msg.code === 'busy' && !settled) {
            clearTimeout(to)
            try { this.ws?.close() } catch {}
            done(reject, err)
          }
        }
      }
      this.ws.onerror = () => {
        clearTimeout(to)
        const err = new Error('Voice stream error')
        this.onError?.(err)
        done(reject, err)
      }
      this.ws.onclose = () => {
        clearTimeout(to)
        this.connected = false
        this._finalResolvers.splice(0).forEach((r) => r(''))
        if (!settled) done(reject, new Error('Voice stream closed'))
      }
    })
  }

  sendAudio(blobOrBuffer) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false
    try {
      this.ws.send(blobOrBuffer)
      return true
    } catch {
      return false
    }
  }

  flush() {
    return new Promise((resolve) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) { resolve(''); return }
      this._finalResolvers.push(resolve)
      try { this.ws.send(JSON.stringify({ type: 'flush' })) } catch { resolve('') }
      setTimeout(() => {
        const i = this._finalResolvers.indexOf(resolve)
        if (i >= 0) { this._finalResolvers.splice(i, 1); resolve('') }
      }, 30000)
    })
  }

  reset() {
    try { this.ws?.send(JSON.stringify({ type: 'reset' })) } catch {}
  }

  close() {
    try { this.ws?.close() } catch {}
    this.ws = null
    this.connected = false
  }
}

// Try to open a stream; return null if WS unavailable so callers use REST.
export async function tryVoiceStream(opts) {
  try {
    const s = new VoiceStream(opts)
    await s.connect()
    return s
  } catch {
    return null
  }
}
