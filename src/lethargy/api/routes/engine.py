from fastapi import APIRouter

from lethargy.engine.registry import ENGINES, LATEST

router = APIRouter(prefix="/v1/engine", tags=["engine"])


@router.get("/versions")
async def get_engine_versions() -> dict:
    return {"latest": LATEST, "known": sorted(ENGINES.keys())}
