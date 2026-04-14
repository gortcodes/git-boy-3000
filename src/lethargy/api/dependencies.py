from fastapi import Request

from lethargy.collector.client import GitHubClient


def get_github_client(request: Request) -> GitHubClient:
    return request.app.state.github_client
