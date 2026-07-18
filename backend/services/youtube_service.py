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
            has_transcript = bool(transcript_text)
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
        }

        if has_transcript:
            result["transcript"] = transcript_text
        else:
            # No transcript — use description + metadata as context
            # The LLM can still generate useful content from this
            result["transcript"] = ""
            result["note"] = (
                "This video does not have captions/subtitles. "
                "Summary and study tools are based on the video title and description."
            )

        return result

    def _fetch_transcript(self, video_id: str) -> str:
        """Fetch transcript using youtube_transcript_api v1.2.4+ API."""
        from youtube_transcript_api import YouTubeTranscriptApi

        ytt = YouTubeTranscriptApi()

        # Try to fetch directly (tries English first, then any available)
        try:
            transcript = ytt.fetch(video_id, languages=["en"])
        except Exception:
            # Try listing available transcripts and pick any
            try:
                tl = ytt.list(video_id)
                transcript = tl.find_transcript(["en"]).fetch()
            except Exception:
                try:
                    tl = ytt.list(video_id)
                    for t in tl:
                        transcript = t.fetch()
                        break
                except Exception:
                    return ""

        if not transcript:
            return ""

        # Combine all entries into full text
        lines = []
        for entry in transcript:
            text = entry.text.strip()
            if text:
                # Clean up common transcript artifacts
                text = re.sub(r'\[.*?\]', '', text)  # Remove [Music], [Applause], etc.
                text = re.sub(r'♪.*?♪', '', text)    # Remove music notes
                text = text.strip()
                if text:
                    lines.append(text)

        return " ".join(lines)

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

        # Description + duration from page scraping
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
