from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from lethargy.api.dependencies import get_github_client
from lethargy.collector.client import GitHubClient
from lethargy.collector.errors import UserNotFound

USERNAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$"

router = APIRouter(prefix="/v1/sheet", tags=["sheet"])


@router.get("/{username}")
async def get_sheet(
    username: Annotated[str, Path(pattern=USERNAME_PATTERN)],
    github: Annotated[GitHubClient, Depends(get_github_client)],
) -> dict:
    try:
        profile = await github.get_profile(username)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="user not found") from None
    return {"profile": profile}
