from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from lethargy.api.dependencies import get_github_client
from lethargy.collector.client import GitHubClient
from lethargy.collector.errors import (
    GitHubUnavailable,
    RateLimited,
    RateLimitFloorHit,
    UserNotFound,
)

router = APIRouter(prefix="/v1/repos", tags=["repos"])


@router.get("/{username}")
async def list_repos(
    username: str,
    client: Annotated[GitHubClient, Depends(get_github_client)],
) -> list:
    try:
        return await client.list_user_repos(username)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="user not found") from None
    except (RateLimited, RateLimitFloorHit) as exc:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else {}
        status = 429 if isinstance(exc, RateLimited) else 503
        raise HTTPException(status_code=status, detail="rate limited", headers=headers) from None
    except GitHubUnavailable as exc:
        raise HTTPException(status_code=502, detail=f"github unavailable: {exc}") from None


@router.get("/{owner}/{name}/tree")
async def get_repo_tree(
    owner: str,
    name: str,
    client: Annotated[GitHubClient, Depends(get_github_client)],
    branch: Annotated[str, Query()] = "main",
) -> dict:
    try:
        paths = await client.get_repo_tree(owner, name, branch)
        return {"paths": paths}
    except GitHubUnavailable as exc:
        raise HTTPException(status_code=502, detail=f"github unavailable: {exc}") from None
