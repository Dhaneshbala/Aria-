from fastapi import APIRouter
from pydantic import BaseModel
from ..services.research_service import ResearchService
from ..services.youtube_service import YouTubeService

router = APIRouter(prefix="/api/research", tags=["research"])
research_svc = ResearchService()
youtube_svc = YouTubeService()


class SearchRequest(BaseModel):
    query: str


class YouTubeRequest(BaseModel):
    url: str


@router.post("/search")
async def web_search(req: SearchRequest):
    results = await research_svc.search(req.query)
    return {"results": results}


@router.post("/youtube")
async def process_youtube(req: YouTubeRequest):
    result = await youtube_svc.process(req.url)
    return result
