from fastapi import Request

from lethargy.collector.client import GitHubClient
from lethargy.config import Settings
from lethargy.persistence.db import Database
from lethargy.services.replay_service import ReplayService
from lethargy.services.sheet_service import SheetService


def get_github_client(request: Request) -> GitHubClient:
    return request.app.state.github_client


def get_sheet_service(request: Request) -> SheetService:
    return request.app.state.sheet_service


def get_replay_service(request: Request) -> ReplayService:
    return request.app.state.replay_service


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings
