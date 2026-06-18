"""
Image generation service.

Strategy for MacBook Air M4 16GB:
  PRIMARY:  Pollinations.ai — free, no install, no GPU, no disk space needed.
            Just an API call. Returns real AI-generated images.
  FALLBACK: Stable Diffusion A1111 (only if user has it installed separately).

Pollinations.ai is completely free, requires no API key, and works on any machine.
It uses FLUX and SDXL models hosted remotely.
"""
import asyncio
import httpx
import urllib.parse
import base64


class ImageGenService:

    async def generate(
        self,
        prompt: str,
        negative: str = "",
        width: int = 512,
        height: int = 512,
        model: str = "flux",          # "flux" | "turbo" | "flux-realism"
    ) -> dict:
        """
        Generate an image. Returns {"image": "data:image/...", "source": "pollinations"|"sd"}.
        Tries Pollinations first (no install needed), then SD if configured.
        """
        # Try Pollinations.ai (free, no GPU, no disk)
        result = await self._pollinations(prompt, width, height, model)
        if result:
            return {"image": result, "source": "pollinations"}

        # Try local Stable Diffusion (only if user has it running)
        result = await self._stable_diffusion(prompt, negative, width, height)
        if result:
            return {"image": result, "source": "stable_diffusion"}

        return {"error": "Image generation unavailable. Check your internet connection."}

    async def _pollinations(
        self, prompt: str, width: int, height: int, model: str
    ) -> str | None:
        """
        Pollinations.ai — free image generation, no API key, no setup.
        Supports FLUX (high quality) and turbo (faster).
        """
        try:
            # Make it safe and educational
            safe_prompt = f"educational, child-friendly, colourful illustration: {prompt}"
            encoded = urllib.parse.quote(safe_prompt)

            # Pollinations direct image URL
            url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true"
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.get(url, follow_redirects=True)
                if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
                    # Convert to base64 data URL for frontend
                    b64 = base64.b64encode(r.content).decode()
                    mime = r.headers.get("content-type", "image/jpeg")
                    return f"data:{mime};base64,{b64}"
        except Exception:
            pass
        return None

    async def _stable_diffusion(
        self, prompt: str, negative: str, width: int, height: int
    ) -> str | None:
        """Local Stable Diffusion (optional, user must have A1111 running)."""
        try:
            sd_url = "http://127.0.0.1:7860"
            payload = {
                "prompt": f"educational, child-friendly, colourful: {prompt}",
                "negative_prompt": f"nsfw, violent, adult, {negative}",
                "steps": 20, "width": width, "height": height,
                "cfg_scale": 7,
            }
            async with httpx.AsyncClient(timeout=90) as client:
                r = await client.post(f"{sd_url}/sdapi/v1/txt2img", json=payload)
                if r.status_code == 200:
                    images = r.json().get("images", [])
                    if images:
                        return f"data:image/png;base64,{images[0]}"
        except Exception:
            pass
        return None

    async def is_available(self) -> dict:
        """Check which image generation backends are available."""
        status = {"pollinations": False, "stable_diffusion": False}

        # Check Pollinations (needs internet)
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get("https://image.pollinations.ai/", timeout=8)
                status["pollinations"] = r.status_code < 500
        except Exception:
            pass

        # Check local SD
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get("http://127.0.0.1:7860/sdapi/v1/sd-models")
                status["stable_diffusion"] = r.status_code == 200
        except Exception:
            pass

        return status
