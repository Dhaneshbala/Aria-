"""YouTube service — extracts transcripts and video metadata, generates summaries."""
import asyncio
import re
from typing import Optional


class YouTubeService:

    async def process(self, url: str) -> dict:
        video_id = self._extract_id(url)
        if not video_id:
            return {"error": "Invalid YouTube URL"}
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_sync, video_id)

    def _extract_id(self, url: str) -> Optional[str]:
        patterns = [
            r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
            r"embed/([A-Za-z0-9_-]{11})",
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return None

    def _fetch_sync(self, video_id: str) -> dict:
        import httpx

        # Step 1: Get video metadata from page (always works)
        metadata = self._scrape_metadata(video_id)

        # Step 2: Try to get transcript
        transcript_text = ""
        has_transcript = False
        try:
            transcript_text = self._fetch_transcript(video_id)
            has_transcript = bool(transcript_text and transcript_text.strip())
        except Exception:
            pass

        # Step 2b: No captions — try audio transcription via yt-dlp + Whisper
        if not has_transcript:
            try:
                audio_text = self._transcribe_audio_fallback(video_id)
                if audio_text and len(audio_text.strip()) > 40:
                    transcript_text = audio_text.strip()
                    has_transcript = True
            except Exception:
                pass

        # Step 3: Build result
        result = {
            "video_id": video_id,
            "title": metadata.get("title", f"YouTube Video {video_id}"),
            "channel": metadata.get("channel", ""),
            "duration_minutes": metadata.get("duration_minutes", 0),
            "description": metadata.get("description", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "has_transcript": has_transcript,
            "tags": metadata.get("tags", []),
        }

        if has_transcript:
            result["transcript"] = transcript_text
            # Generate AI summary even with transcript for quick overview
            try:
                result["ai_summary"] = self._llm_summary_sync(result["title"], transcript_text[:4000], metadata.get("description","")[:800])
            except Exception:
                result["ai_summary"] = ""
        else:
            # No transcript at all — generate AI analysis from title/description/tags
            result["transcript"] = ""
            # Try LLM to create a useful analysis from metadata
            try:
                ai_analysis = self._llm_summary_sync(result["title"], "", metadata.get("description",""), metadata.get("tags",[]))
                result["ai_summary"] = ai_analysis
                # Treat AI analysis as transcript-like content so quiz/flashcards still work
                result["transcript"] = ai_analysis
                result["has_transcript"] = True if ai_analysis else False
                result["fallback"] = "audio"
            except Exception:
                result["ai_summary"] = ""
                result["fallback"] = "metadata"
            result["note"] = (
                "No captions found — analysed via audio transcription and AI inference from title/description."
                if result.get("has_transcript") else
                "This video has no captions. Analysis is based on title, description and tags."
            )

        return result

    def _transcribe_audio_fallback(self, video_id: str) -> str:
        """Download audio via yt-dlp and transcribe with faster-whisper/whisper."""
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path
        if not shutil.which("yt-dlp"):
            return ""
        try:
            with tempfile.TemporaryDirectory() as td:
                tmpl = str(Path(td) / f"{video_id}.%(ext)s")
                url = f"https://www.youtube.com/watch?v={video_id}"
                # Download best audio, limit to 8 minutes to avoid huge files
                cmd = [
                    "yt-dlp", "-f", "bestaudio/best",
                    "--extract-audio", "--audio-format", "mp3",
                    "--audio-quality", "5",
                    "-o", tmpl,
                    "--no-playlist", "--quiet",
                    url,
                ]
                subprocess.run(cmd, timeout=60, capture_output=True)
                # Find downloaded file
                files = list(Path(td).glob(f"{video_id}.*"))
                if not files:
                    return ""
                audio_file = files[0]
                if audio_file.stat().st_size < 1024:
                    return ""
                # Transcribe with VoiceService
                try:
                    from services.voice_service import VoiceService
                    vs = VoiceService()
                    # Run sync transcribe in thread
                    text = vs._transcribe_sync(audio_file.read_bytes(), "audio/mp3")
                    if text and "not available" not in text.lower():
                        return text[:8000]
                except Exception:
                    pass
                # Fallback: try faster-whisper directly
                try:
                    from faster_whisper import WhisperModel
                    model = WhisperModel("base", device="cpu", compute_type="int8")
                    segs, _ = model.transcribe(str(audio_file))
                    return " ".join(s.text for s in segs)[:8000]
                except Exception:
                    pass
        except Exception:
            pass
        return ""

    def _llm_summary_sync(self, title: str, transcript: str, description: str, tags: list | None = None) -> str:
        """Generate an AI summary via Ollama for videos without transcript."""
        import httpx
        import os
        try:
            from models.database import MODELS as _MODELS, OLLAMA_URL as _OURL
            ollama_url = _OURL
            model = _MODELS.get("main", "gemma4:e4b-mlx")
        except Exception:
            ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/").split("/api")[0]
            model = os.environ.get("ARIA_MAIN_MODEL", "gemma4:e4b-mlx")
        tags_str = ", ".join((tags or [])[:10])
        # Build prompt
        if transcript:
            prompt = f"Video Title: {title}\nDescription: {description[:600]}\nTranscript excerpt: {transcript[:2000]}\n\nWrite a concise 150-200 word summary of what this video covers, key points, and who it's for. No intro, just the summary."
        else:
            prompt = f"Video Title: {title}\nDescription: {description[:1000]}\nTags: {tags_str}\n\nThis YouTube video has no transcript. Using only the title, description and tags, infer and write a helpful 150-200 word overview of what the video is about, likely key topics, and 3 bullet key takeaways. Be clear this is inferred from metadata. No hallucinating timestamps."
        try:
            r = httpx.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_ctx": 4096, "num_predict": 400, "temperature": 0.6},
                },
                timeout=25,
            )
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "").strip()[:2000]
        except Exception:
            pass
        return ""

    def _fetch_transcript(self, video_id: str) -> str:
        """Fetch transcript — supports both youtube_transcript_api 0.6 and 1.2+."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except Exception:
            return ""
        # Try new API (1.2+): instance methods fetch/list
        try:
            ytt = YouTubeTranscriptApi()
            # Try direct fetch with multiple language fallbacks (covers auto-generated)
            for langs in (["en"], ["en", "en-US", "en-GB"], ["a.en", "en-auto"], None):
                try:
                    if langs is None:
                        transcript = ytt.fetch(video_id)
                    else:
                        transcript = ytt.fetch(video_id, languages=langs)
                    if transcript:
                        break
                except Exception:
                    continue
            else:
                transcript = None

            if not transcript:
                # Try listing available transcripts and pick any (including auto)
                try:
                    tl = ytt.list(video_id)
                    for pref in (["en"], ["en-US", "en-GB"], None):
                        try:
                            if pref is None:
                                for t in tl:
                                    transcript = t.fetch()
                                    break
                            else:
                                transcript = tl.find_transcript(pref).fetch()
                            if transcript:
                                break
                        except Exception:
                            continue
                except Exception:
                    transcript = None
            if transcript:
                # Combine and return
                lines = []
                for entry in transcript:
                    try:
                        text = entry.text.strip() if hasattr(entry, 'text') else str(entry).strip()
                    except Exception:
                        text = ""
                    if text:
                        text = re.sub(r'\[.*?\]', '', text)
                        text = re.sub(r'♪.*?♪', '', text)
                        text = text.strip()
                        if text:
                            lines.append(text)
                if lines:
                    return " ".join(lines)
        except Exception:
            pass
        # Fallback old API (0.6): static methods get_transcript / list_transcripts
        try:
            from youtube_transcript_api import YouTubeTranscriptApi as OldAPI
            # Try old static API
            for langs in (["en"], ["en", "en-US"], None):
                try:
                    if langs is None:
                        transcript = OldAPI.get_transcript(video_id)
                    else:
                        transcript = OldAPI.get_transcript(video_id, languages=langs)
                    if transcript:
                        lines = []
                        for entry in transcript:
                            text = entry.get("text","").strip() if isinstance(entry, dict) else str(entry).strip()
                            if text:
                                text = re.sub(r'\[.*?\]', '', text)
                                text = re.sub(r'♪.*?♪', '', text)
                                text = text.strip()
                                if text:
                                    lines.append(text)
                        if lines:
                            return " ".join(lines)
                except Exception:
                    continue
            # Try list_transcripts old API
            try:
                transcripts = OldAPI.list_transcripts(video_id)
                for t in transcripts:
                    try:
                        data = t.fetch()
                        lines = []
                        for entry in data:
                            text = entry.get("text","").strip() if isinstance(entry, dict) else str(entry).strip()
                            if text:
                                lines.append(text)
                        if lines:
                            return " ".join(lines)
                    except Exception:
                        continue
            except Exception:
                pass
        except Exception:
            pass
        return ""

    def _scrape_metadata(self, video_id: str) -> dict:
        """Scrape video metadata from the YouTube page."""
        import httpx

        result = {}

        # Title + channel from oEmbed (fast, reliable)
        try:
            r = httpx.get(
                f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json",
                timeout=5
            )
            if r.status_code == 200:
                data = r.json()
                result["title"] = data.get("title", "")
                result["channel"] = data.get("author_name", "")
        except Exception:
            pass

        # Description + duration + tags from page scraping
        try:
            r = httpx.get(
                f"https://www.youtube.com/watch?v={video_id}",
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            )
            if r.status_code == 200:
                html = r.text

                # Description from meta tag
                desc_match = re.search(r'<meta name="description" content="([^"]+)"', html)
                if desc_match:
                    result["description"] = desc_match.group(1)

                # Also try to get longer description from structured data
                desc_match2 = re.search(r'"shortDescription":"(.*?)"', html)
                if desc_match2:
                    desc = desc_match2.group(1)
                    desc = desc.replace('\\n', '\n').replace('\\"', '"')
                    if len(desc) > len(result.get("description", "")):
                        result["description"] = desc[:2000]

                # Tags
                tags_match = re.search(r'"keywords":\s*\[(.*?)\]', html)
                if tags_match:
                    try:
                        import json as _js
                        tags = _js.loads(f"[{tags_match.group(1)}]")
                        result["tags"] = [t for t in tags if isinstance(t, str)][:12]
                    except Exception:
                        pass

                # Duration
                dur_match = re.search(r'"lengthSeconds":"(\d+)"', html)
                if dur_match:
                    result["duration_minutes"] = round(int(dur_match.group(1)) / 60, 1)

                # Title fallback from page
                if not result.get("title"):
                    title_match = re.search(r'"title":"([^"]+)"', html)
                    if title_match:
                        result["title"] = title_match.group(1)

        except Exception:
            pass

        return result
