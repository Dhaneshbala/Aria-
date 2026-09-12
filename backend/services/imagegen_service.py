"""
Image generation service — How top models do it, made local.

Top diffusion models (FLUX.1, SDXL, Sana) work by latent diffusion:
  text -> CLIP/T5 encoder -> latent noise -> iterative denoising (DiT/U-Net) -> VAE decode -> pixels.
ARIA doesn't run that 12B param model locally on 16GB (would OOM). Instead:

  PRIMARY:  Pollinations.ai — free, no GPU, no install. Remote FLUX/Sana diffusion,
            same architecture as top models, just hosted remotely. Returns real AI images.
  FALLBACK: Local Stable Diffusion A1111 (if user has it installed at 127.0.0.1:7860).

Pollinations is completely free, needs no API key, and uses FLUX/Sana models.
"""
import asyncio
import httpx
import urllib.parse
import base64
import logging

logger = logging.getLogger(__name__)


class ImageGenService:

    async def generate(
        self,
        prompt: str,
        negative: str = "",
        width: int = 512,
        height: int = 512,
        model: str = "flux",          # "flux" | "turbo" | "sana"
    ) -> dict:
        """
        Generate an image. Returns {"image": "data:image/...", "source": "pollinations"|"sd"}.
        Tries Pollinations first (no install needed), then SD if configured.
        """
        # Try Pollinations.ai (free, no GPU, no disk) — this IS diffusion (FLUX DiT)
        result = await self._pollinations(prompt, width, height, model)
        if result:
            return {"image": result, "source": "pollinations"}

        # Try local Stable Diffusion (only if user has it running)
        result = await self._stable_diffusion(prompt, negative, width, height)
        if result:
            return {"image": result, "source": "stable_diffusion"}

        return {"error": "Image generation unavailable. Check your internet connection. Pollinations.ai may be rate-limited — try again in 30 seconds."}

    async def _pollinations(
        self, prompt: str, width: int, height: int, model: str
    ) -> str | None:
        """
        Pollinations.ai — free image generation via remote diffusion (FLUX/Sana).
        Same latent diffusion as top models, just hosted remotely.
        """
        try:
            # Safe, educational prefix — keeps ARIA kid-friendly
            safe_prompt = f"educational, child-friendly, colourful illustration: {prompt}"
            encoded = urllib.parse.quote(safe_prompt)

            # Pollinations direct image URL — supports flux, turbo, sana
            # enhance=true lets Pollinations refine prompt via LLM before diffusion
            url = (
                f"https://image.pollinations.ai/prompt/{encoded}"
                f"?width={width}&height={height}&model={model}"
                f"&nologo=true&enhance=true"
            )

            async with httpx.AsyncClient(timeout=60, follow_redirects=True, verify=False) as client:
                r = await client.get(url, follow_redirects=True)
                ct = r.headers.get("content-type", "")
                # Success: image/*
                if r.status_code == 200 and ct.startswith("image/"):
                    b64 = base64.b64encode(r.content).decode()
                    mime = ct.split(";")[0] or "image/jpeg"
                    return f"data:{mime};base64,{b64}"
                # Rate-limit / x402 payment required — Pollinations returns JSON with x402Version
                if r.status_code in (402, 429) or "application/json" in ct:
                    try:
                        j = r.json()
                        if j.get("x402Version") or "Queue full" in str(j.get("error", "")):
                            logger.warning("Pollinations rate-limited: %s", j.get("error"))
                            return None
                    except Exception:
                        pass
                    logger.warning("Pollinations returned %s: %s", r.status_code, r.text[:300])
        except Exception as e:
            logger.debug("Pollinations failed: %s", e)
        return None

    async def _stable_diffusion(
        self, prompt: str, negative: str, width: int, height: int
    ) -> str | None:
        """Local Stable Diffusion (optional, user must have A1111 running at 127.0.0.1:7860)."""
        try:
            # Allow env override for SD URL
            import os
            sd_url = os.environ.get("SD_URL", "http://127.0.0.1:7860")
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
        except Exception as e:
            logger.debug("Local SD failed: %s", e)
        return None

    async def is_available(self) -> dict:
        """Check which image generation backends are available."""
        status = {"pollinations": False, "stable_diffusion": False}

        # Check Pollinations (needs internet) — HEAD is lighter than GET
        try:
            async with httpx.AsyncClient(timeout=8, verify=False) as client:
                r = await client.get("https://image.pollinations.ai/", timeout=8, follow_redirects=True)
                # Pollinations returns HTML on root; 200 means reachable
                status["pollinations"] = r.status_code < 500
        except Exception:
            pass

        # Check local SD
        try:
            import os
            sd_url = os.environ.get("SD_URL", "http://127.0.0.1:7860")
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{sd_url}/sdapi/v1/sd-models")
                status["stable_diffusion"] = r.status_code == 200
        except Exception:
            pass

        return status
