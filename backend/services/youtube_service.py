"""YouTube service — extracts transcripts and structures content."""
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
        try:
            from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = None
            # Try English first
            try:
                transcript = transcript_list.find_transcript(["en"]).fetch()
            except Exception:
                # Any available language
                try:
                    transcript = transcript_list.find_generated_transcript(["en"]).fetch()
                except Exception:
                    for t in transcript_list:
                        transcript = t.fetch()
                        break

            if not transcript:
                return {"error": "No transcript available for this video"}

            full_text = " ".join(entry.get("text", "") for entry in transcript)
            # Get title from oEmbed
            title = self._get_title(video_id)

            return {
                "video_id": video_id,
                "title": title,
                "transcript": full_text,
                "duration_minutes": round(transcript[-1].get("start", 0) / 60, 1) if transcript else 0,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        except Exception as e:
            return {"error": f"Could not fetch transcript: {e}"}

    def _get_title(self, video_id: str) -> str:
        try:
            import httpx
            r = httpx.get(
                f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json",
                timeout=5
            )
            return r.json().get("title", f"YouTube Video {video_id}")
        except Exception:
            return f"YouTube Video {video_id}"
