from fastapi import APIRouter
from pydantic import BaseModel
from services.imagegen_service import ImageGenService
from models.database import get_config

router = APIRouter(prefix="/api/imagegen", tags=["imagegen"])
sd = ImageGenService()


class ImageRequest(BaseModel):
    prompt:  str
    negative: str = ""
    width:   int  = 512
    height:  int  = 512
    model:   str  = "flux"     # "flux" | "turbo" | "sana" | "flux-realism"


@router.post("/generate")
async def generate_image(req: ImageRequest):
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
