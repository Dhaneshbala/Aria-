"""ARIA Backend — FastAPI main entry point."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import (
    chat_router, study_router, docs_router,
    research_router, voice_router, imagegen_router, admin_router, agent_router,
    intelligence_router, v2_router, planner_router
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="ARIA — AI Study Assistant", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in [
    chat_router, study_router, docs_router,
    research_router, voice_router, imagegen_router, admin_router, agent_router,
    intelligence_router, v2_router, planner_router
]:
    app.include_router(router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
