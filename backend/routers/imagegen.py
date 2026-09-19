from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from services.imagegen_service import ImageGenService
from models.database import get_config

router = APIRouter(prefix="/api/imagegen", tags=["imagegen"])
sd = ImageGenService()

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from config.settings import get_settings as _get_img_settings
    _img_limit_val = _get_img_settings().rate_limit_chat
    _img_limiter = Limiter(key_func=get_remote_address, default_limits=[_img_limit_val])
    _img_limit = _img_limiter.limit(_img_limit_val)
except Exception:
    _img_limit = lambda f: f  # no-op


class ImageRequest(BaseModel):
    prompt:  str = Field(..., min_length=1, max_length=2000)
    negative: str = Field(default="", max_length=1000)
    width:   int  = Field(default=512, ge=64, le=2048)
    height:  int  = Field(default=512, ge=64, le=2048)
    model:   str  = Field(default="flux", max_length=50)


@router.post("/generate")
@_img_limit
async def generate_image(req: ImageRequest, request: Request):
    config = get_config()
    poll_model = config.get("pollinations_model", "flux")
    # Allow request to override, but config is source of truth if req uses default
    model = req.model if req.model != "flux" or poll_model == "flux" else poll_model
    # If config has explicit model, use it
    if config.get("pollinations_model"):
        model = config["pollinations_model"]
    elif req.model:
        model = req.model
    result = await sd.generate(
        req.prompt, req.negative, req.width, req.height,
        model=model
    )
    return result


@router.get("/status")
async def image_gen_status():
    status = await sd.is_available()
    return {
        "pollinations": status.get("pollinations", False),
        "stable_diffusion": status.get("stable_diffusion", False),
        "recommended": "pollinations",
        "note": "Pollinations.ai uses remote FLUX/Sana diffusion — same latent diffusion as top models, no local GPU needed.",
    }
