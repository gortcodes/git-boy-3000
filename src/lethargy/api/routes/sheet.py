from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from lethargy.api.dependencies import (
    get_database,
    get_replay_service,
    get_settings_dep,
    get_sheet_service,
)
from lethargy.collector.errors import GitHubUnavailable, RateLimited, UserNotFound
from lethargy.config import Settings
from lethargy.engine.domain import CharacterSheet
from lethargy.persistence.db import Database
from lethargy.persistence.sheets import list_sheets_for_user
from lethargy.services.errors import NoHistoryAvailable, UnknownEngineVersion
from lethargy.services.replay_service import ReplayService
from lethargy.services.sheet_service import SheetService

USERNAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$"

router = APIRouter(prefix="/v1/sheet", tags=["sheet"])


def _set_sheet_headers(response: Response, sheet: CharacterSheet) -> None:
    response.headers["X-Engine-Version"] = str(sheet.engine_version)
    response.headers["X-Raw-Schema-Version"] = str(sheet.raw_schema_version)
    response.headers["X-Fetched-At"] = sheet.fetched_at.isoformat()


def _translate_collector_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, UserNotFound):
        return HTTPException(status_code=404, detail="user not found")
    if isinstance(exc, RateLimited):
        return HTTPException(status_code=429, detail="github rate limited")
    if isinstance(exc, GitHubUnavailable):
        return HTTPException(status_code=502, detail=f"github unavailable: {exc}")
    raise exc


@router.get("/{username}")
async def get_sheet(
    username: Annotated[str, Path(pattern=USERNAME_PATTERN)],
    service: Annotated[SheetService, Depends(get_sheet_service)],
    response: Response,
) -> dict:
    try:
        bundle = await service.get_or_refresh(username)
    except (UserNotFound, RateLimited, GitHubUnavailable) as exc:
        raise _translate_collector_errors(exc) from None

    _set_sheet_headers(response, bundle.sheet)
    return _to_response(bundle.sheet)


@router.get("/{username}/raw")
async def get_sheet_raw(
    username: Annotated[str, Path(pattern=USERNAME_PATTERN)],
    service: Annotated[SheetService, Depends(get_sheet_service)],
    response: Response,
) -> dict:
    try:
        bundle = await service.get_or_refresh(username)
    except (UserNotFound, RateLimited, GitHubUnavailable) as exc:
        raise _translate_collector_errors(exc) from None

    _set_sheet_headers(response, bundle.sheet)
    body = _to_response(bundle.sheet)
    body["signals"] = asdict(bundle.signals)
    return body


@router.post("/{username}/recompute")
async def recompute_sheet(
    username: Annotated[str, Path(pattern=USERNAME_PATTERN)],
    engine_version: Annotated[int, Query(alias="engine", ge=1)],
    service: Annotated[ReplayService, Depends(get_replay_service)],
    response: Response,
) -> dict:
    try:
        sheet = await service.recompute(username, engine_version)
    except UnknownEngineVersion:
        raise HTTPException(status_code=400, detail="unknown engine version") from None
    except NoHistoryAvailable:
        raise HTTPException(status_code=404, detail="no history for this user") from None

    _set_sheet_headers(response, sheet)
    return _to_response(sheet)


@router.get("/{username}/history")
async def get_sheet_history(
    username: Annotated[str, Path(pattern=USERNAME_PATTERN)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    database: Annotated[Database, Depends(get_database)],
) -> dict:
    if username.lower() not in settings.owner_usernames:
        raise HTTPException(status_code=404, detail="no history for this user") from None

    async with database.session() as session:
        rows = await list_sheets_for_user(session, username)

    history = [
        {
            "id": row["id"],
            "engine_version": row["engine_version"],
            "computed_at": row["computed_at"].isoformat(),
            "stats": row["stats"],
            "flavor": row["flavor"],
        }
        for row in rows
    ]
    return {"username": username, "history": history}


def _to_response(sheet: CharacterSheet) -> dict:
    return {
        "username": sheet.username,
        "engine_version": sheet.engine_version,
        "raw_schema_version": sheet.raw_schema_version,
        "fetched_at": sheet.fetched_at.isoformat(),
        "computed_at": sheet.computed_at.isoformat(),
        "stats": {
            name: {
                "name": stat.name,
                "value": stat.value,
                "raw_score": stat.raw_score,
                "inputs": stat.contributing_signals,
            }
            for name, stat in sheet.stats.items()
        },
        "flavor": sheet.flavor,
    }
