"""Day 29: baseline voice latency budget on this Mac (no new deps).

Measures what the streaming engine replacement must beat:
  1. TTS (`say`) seconds per sentence: short / medium / Tamil
  2. STT (faster-whisper small) cold load vs warm transcribe of ~5 s audio
  3. Peak RSS delta of the whisper load (via resource.ru_maxrss)

Read-only: writes temp audio under the system temp dir, cleans up after.
Usage:  python3 backend/scripts/bench_voice.py
"""

import asyncio
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SENTENCES = {
    "short_en": "Well done!",
    "medium_en": "Photosynthesis turns sunlight, water and carbon dioxide into glucose and oxygen.",
    "math_en": "Solve x squared plus three equals seven.",
    "short_ta": "நன்று!",
}

TTS_ROUNDS = 3


async def bench_tts():
    from services.voice_service import VoiceService

    svc = VoiceService()
    out = {}
    for name, text in SENTENCES.items():
        lang = "ta" if name.endswith("_ta") else "en"
        times = []
        for _ in range(TTS_ROUNDS):
            t0 = time.perf_counter()
            data = await svc.synthesize(text, lang)
            dt = time.perf_counter() - t0
            times.append(dt)
            assert data, f"empty TTS for {name}"
        out[name] = {"median_s": round(statistics.median(times), 3), "bytes": len(data)}
    return out


def _rss_mb() -> float:
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    except Exception:
        return -1.0


def bench_stt():
    from services.voice_service import VoiceService

    svc = VoiceService()
    # 5 s of speech via `say` so whisper has something real to chew on
    wav = Path(tempfile.gettempdir()) / "aria_bench_5s.aiff"
    subprocess.run(
        [
            "say",
            "-o",
            str(wav),
            "Photosynthesis turns sunlight and water into glucose. " * 3,
        ],
        check=True,
        timeout=120,
    )
    try:
        data = wav.read_bytes()
        rss_before = _rss_mb()
        t0 = time.perf_counter()
        cold = asyncio.run(svc.transcribe(data, "audio/aiff", "en"))
        cold_s = time.perf_counter() - t0
        rss_after = _rss_mb()
        t0 = time.perf_counter()
        warm = asyncio.run(svc.transcribe(data, "audio/aiff", "en"))
        warm_s = time.perf_counter() - t0
        return {
            "audio_kb": len(data) // 1024,
            "cold_s": round(cold_s, 2),
            "warm_s": round(warm_s, 2),
            "rss_delta_mb": round(rss_after - rss_before, 1),
            "text_prefix": (cold.get("text", "") or "")[:60],
        }
    finally:
        wav.unlink(missing_ok=True)


def bench_live_turn(
    base="http://127.0.0.1:8000", prompt="Why is the sky blue? One short paragraph."
):
    """Day 41: full spoken-turn latency against a RUNNING server.

    Measures LLM time-to-first-text (TTFS) over SSE + Piper sentence-1
    synth time → estimated TTFA. Skips gracefully if the server is down.
    Usage: python3 backend/scripts/bench_voice.py --live [base_url]
    """
    import json
    import urllib.parse
    import urllib.request

    try:
        urllib.request.urlopen(base + "/api/health", timeout=10).read()
    except Exception as e:
        print(f"live bench skipped: server not reachable at {base} ({e})")
        return None
    t0 = time.perf_counter()
    req = urllib.request.Request(
        base + "/api/chat",
        data=urllib.parse.urlencode({"message": prompt, "mode": "voice"}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    ttfs, reply = None, ""
    with urllib.request.urlopen(req, timeout=300) as r:
        buf = ""
        while True:
            chunk = r.read(64).decode("utf-8", "replace")
            if not chunk:
                break
            buf += chunk
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if line.startswith("data: "):
                    try:
                        d = json.loads(line[6:])
                    except Exception:
                        continue
                    if d.get("type") == "text":
                        if ttfs is None:
                            ttfs = time.perf_counter() - t0
                        reply += d.get("content", "")
    import re

    s1 = re.split(r"(?<=[.!?])\s+", reply.strip())[0] if reply.strip() else ""
    t1 = time.perf_counter()
    sreq = urllib.request.Request(
        base + "/api/voice/synthesize",
        data=json.dumps({"text": s1[:350]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(sreq, timeout=120) as sr:
        audio, engine = sr.read(), sr.headers.get("X-Engine")
    synth_s = time.perf_counter() - t1
    print(f"== live turn ({base}) ==")
    print(
        f"  TTFS={ttfs:.1f}s reply_chars={len(reply)} synth1={synth_s:.2f}s engine={engine}"
    )
    print(f"  TTFA_est={ttfs + synth_s:.1f}s first_sentence={s1[:80]!r}")
    return {"ttfs": round(ttfs, 1), "synth1": round(synth_s, 2), "engine": engine}


def main():
    if "--live" in sys.argv:
        base = next(
            (a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8000"
        )
        bench_live_turn(base)
        return
    print("== TTS (`say`) ==")
    tts = asyncio.run(bench_tts())
    for name, row in tts.items():
        print(f"  {name:10s} median={row['median_s']}s bytes={row['bytes']}")
    print("== STT (faster-whisper small) ==")
    stt = bench_stt()
    print(
        f"  audio={stt['audio_kb']}KB cold={stt['cold_s']}s warm={stt['warm_s']}s "
        f"rss_delta={stt['rss_delta_mb']}MB"
    )
    print(f"  heard: {stt['text_prefix']!r}")


if __name__ == "__main__":
    main()
