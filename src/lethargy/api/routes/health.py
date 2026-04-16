from typing import Annotated

from fastapi import APIRouter, Depends

from lethargy.api.dependencies import get_settings_dep
from lethargy.config import Settings

router = APIRouter()


@router.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/v1/owner", tags=["config"])
async def owner(
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> dict:
    owners = sorted(settings.owner_usernames)
    return {"owner": owners[0] if owners else None}


@router.get("/privacy", tags=["privacy"])
async def privacy(
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> dict:
    return {
        "contact": settings.privacy_contact or "not configured",
        "removal_requests": (
            "To request removal of any data associated with your GitHub handle, "
            "send an email to the contact address above with your handle. "
            "Non-owner data retention is limited to short-lived caches and "
            "application logs; nothing is persisted to the primary datastore "
            "for users who have not explicitly opted in."
        ),
        "data_retained": [
            "short-lived Redis cache of the current character sheet (expires on TTL)",
            "short-lived Redis cache of GitHub response bodies keyed by ETag",
            "application logs (rotating retention)",
        ],
    }
