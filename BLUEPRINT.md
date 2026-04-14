# lethargy.io — Software Blueprint (v0)

Companion to `PRD.md`. The PRD says *what* and *why*; this says *how*. Every section here should map to code you can actually start writing. Where there's ambiguity, I've made a call and flagged it in §16.

## 0. Orienting principles

- **Owner-only persistence.** Only usernames in `LETHARGY_OWNER_USERNAMES` get durable storage. Every other request is a stateless pass-through: compute, return, forget. This is the privacy model, and it shapes module boundaries.
- **Pure, versioned engine.** Signal extraction and stat scoring are pure functions keyed by `engine_version`. Raw snapshots are stored verbatim so any engine version can recompute any historical sheet on demand.
- **API-first.** The FastAPI service *is* the product. The frontend is disposable and must never be load-bearing for a design decision. If state belongs in the frontend's head, it belongs in the API's response.
- **Observability is code, not ops.** Spans, metrics, and structured logs are wired at module boundaries (collector, engine, persistence, cache), not sprinkled into routes.
- **Defend the rate limit.** Every GitHub call goes through a single client that does ETag conditional requests, updates a Redis-backed gauge, and circuit-breaks at a floor.

## 1. System overview

```
              ┌────────────────┐
              │   user (web)   │
              └────────┬───────┘
                       │ HTTPS
              ┌────────▼───────┐
              │     Caddy      │  TLS + reverse proxy
              └────────┬───────┘
                       │
              ┌────────▼───────┐
              │  FastAPI app   │  /v1/sheet, /healthz, /metrics, /docs
              └─┬────┬────┬────┘
                │    │    │
      ┌─────────┘    │    └──────────┐
      │              │               │
┌─────▼──────┐ ┌─────▼──────┐ ┌──────▼──────┐
│   Redis    │ │ Postgres   │ │   GitHub    │
│  cache +   │ │ owner-only │ │  REST +     │
│  ETag +    │ │ raw snap-  │ │  GraphQL    │
│  locks +   │ │ shots +    │ │             │
│  rate      │ │ computed   │ │             │
│  limit     │ │ sheets     │ │             │
└────────────┘ └────────────┘ └─────────────┘

         Sidecar observability
  ┌─────────┐  ┌──────────┐  ┌────────┐
  │ OTel    │─>│Prometheus│  │  Loki  │
  │collector│  └─────┬────┘  └────┬───┘
  └─────────┘        └────┬───────┘
                          │
                    ┌─────▼──────┐
                    │  Grafana   │  SRE health dashboard only
                    └────────────┘
```

## 2. Runtime topology

Single VPS, docker-compose:

| Service | Image | Role | Exposed |
|---|---|---|---|
| `caddy` | caddy:2 | TLS, reverse proxy | 80/443 |
| `api` | built locally | FastAPI + uvicorn | 8000 (internal) |
| `postgres` | postgres:16 | Durable storage | 5432 (internal) |
| `redis` | redis:7 | Cache, locks, rate-limit state | 6379 (internal) |
| `otel-collector` | otel/opentelemetry-collector-contrib | Span + metric pipeline | 4317 (internal) |
| `prometheus` | prom/prometheus | Metric store | 9090 (internal) |
| `loki` | grafana/loki | Log store | 3100 (internal) |
| `promtail` | grafana/promtail | Docker log shipper | — |
| `grafana` | grafana/grafana | Dashboards | behind `grafana.lethargy.io`, basic auth |

TLS via Caddy's automatic Let's Encrypt. No k8s in v0 — bring k8s in only if it becomes an honest part of the story.

## 3. Module boundaries

Top-level Python package: `lethargy`. Dependency flow is one-way: routes → services → {collector, engine, persistence, cache}. Nothing deeper depends on anything shallower.

```
api  ─┬─> services ─┬─> collector ─┬─> cache (github_etag, rate_limit)
      │             │              └─> github http client
      │             ├─> engine (pure, no IO)
      │             ├─> persistence (owner-only writes)
      │             └─> cache (sheet, lock, throttle)
      └─> obs (middleware)
```

**Rules:**
- `engine/` has no IO, no framework imports, no `asyncio`. Pure functions over frozen dataclasses. This is what makes replay testable and versioning sane.
- `collector/` owns every GitHub IO call. No other module imports `httpx` for GitHub.
- `persistence/` has no opinions about *when* to write — the service layer gates owner-only. Keeping that gate at the call site means the rule is visible, not buried.
- `api/` only orchestrates: request in, service call, response out. No business logic.

## 4. Directory layout

```
lethargy.io/
├── PRD.md
├── BLUEPRINT.md
├── docker-compose.yml
├── docker-compose.override.example.yml
├── Dockerfile
├── Caddyfile
├── pyproject.toml
├── alembic.ini
├── .env.example
├── migrations/versions/
├── grafana/
│   ├── dashboards/lethargy-sre.json
│   └── provisioning/
├── prometheus/prometheus.yml
├── otel/collector.yaml
├── loki/loki-config.yml
├── src/lethargy/
│   ├── __init__.py
│   ├── main.py                 # uvicorn entrypoint
│   ├── config.py               # typed settings from env
│   ├── api/
│   │   ├── app.py              # FastAPI app factory, wiring
│   │   ├── middleware.py       # tracing, correlation id, access log
│   │   ├── schemas.py          # pydantic request/response models
│   │   └── routes/
│   │       ├── sheet.py
│   │       ├── engine.py
│   │       └── health.py
│   ├── services/
│   │   ├── sheet_service.py    # orchestrator: cache → collect → score → persist
│   │   └── replay_service.py   # owner-only historical recompute
│   ├── collector/
│   │   ├── client.py           # GitHub REST + GraphQL, ETag-aware
│   │   ├── fetch.py            # parallel snapshot build
│   │   ├── errors.py
│   │   └── models.py           # typed DTOs for GitHub responses
│   ├── engine/
│   │   ├── domain.py           # RawSnapshot, Signals, Stat, CharacterSheet
│   │   ├── registry.py         # version -> (extract, score)
│   │   ├── v1/
│   │   │   ├── extract.py
│   │   │   └── score.py
│   │   └── luck.py
│   ├── persistence/
│   │   ├── db.py               # async engine, session mgmt
│   │   ├── models.py           # SQLAlchemy table defs
│   │   ├── snapshots.py        # raw_snapshot repository
│   │   └── sheets.py           # computed_sheet repository
│   ├── cache/
│   │   ├── redis.py            # typed wrapper over redis-py async
│   │   ├── github_etag.py
│   │   ├── sheet.py
│   │   ├── lock.py
│   │   ├── throttle.py
│   │   └── rate_limit.py
│   └── obs/
│       ├── tracing.py
│       ├── metrics.py
│       ├── logging.py
│       └── names.py            # span/metric name constants
└── tests/
    ├── conftest.py
    ├── engine/
    │   ├── test_extract_v1.py
    │   ├── test_score_v1.py
    │   └── fixtures/
    │       ├── raw_quiet_user.json
    │       ├── raw_active_user.json
    │       ├── raw_pr_reviewer.json
    │       └── golden/
    │           ├── quiet_user_v1.json
    │           ├── active_user_v1.json
    │           └── pr_reviewer_v1.json
    ├── collector/
    │   ├── test_client.py
    │   └── cassettes/
    ├── services/
    │   └── test_sheet_service.py
    ├── persistence/
    │   └── test_snapshots.py
    └── api/
        └── test_sheet_routes.py
```

## 5. Domain types (engine/domain.py)

Frozen dataclasses, JSON-serializable via a small adapter. No Pydantic in the engine — keep it framework-free so it can be unit-tested without any async or HTTP machinery.

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class RawSnapshot:
    username: str
    fetched_at: datetime
    raw_schema_version: int          # bumps when the collector pulls new fields
    profile: dict                    # /users/{user}
    events: list[dict]               # /users/{user}/events/public
    contributions: dict              # graphql user.contributionsCollection
    gists_meta: dict                 # count + first/latest created_at

@dataclass(frozen=True)
class Signals:
    engine_version: int
    account_age_days: int
    activity_span_days: int
    commits: int
    pushes: int
    prs_authored: int
    pr_reviews: int
    issues_opened: int
    issue_comments: int
    distinct_repos_touched: int
    distinct_external_repos_touched: int
    gists: int
    current_streak_days: int
    longest_streak_days: int
    weekly_commits: list[int]        # 52 slots
    hour_histogram: list[int]        # 24 slots
    restricted_contributions: int    # display-only in v0

@dataclass(frozen=True)
class Stat:
    name: str                        # STR, DEX, CON, INT, WIS, CHA, LUCK
    value: int                       # 1..20 after clamping
    raw_score: float                 # pre-clamp for explainability
    contributing_signals: dict[str, float]

@dataclass(frozen=True)
class CharacterSheet:
    username: str
    engine_version: int
    raw_schema_version: int
    fetched_at: datetime
    computed_at: datetime
    stats: dict[str, Stat]
    flavor: dict                     # circadian, streak details, account age label
```

## 6. Stat engine v1

### 6.1 Pipeline

```
RawSnapshot ──extract_v1──> Signals ──score_v1──> CharacterSheet
```

Both are pure. The registry wires version to functions:

```python
# engine/registry.py
ENGINES: dict[int, Engine] = {
    1: Engine(extract=v1.extract, score=v1.score),
}
LATEST = max(ENGINES)
```

### 6.2 extract_v1 — what it computes

- Event type histogram (PushEvent, PullRequestEvent, PullRequestReviewEvent, IssueCommentEvent, IssuesEvent, CreateEvent, ForkEvent, ReleaseEvent, WatchEvent, PublicEvent).
- Commits per push: sum of `payload.size` across PushEvents, deduplicated by sha within the window to blunt force-push inflation.
- Distinct repos touched. Each classified as own-vs-external by comparing `repo.name.split("/")[0]` to `profile.login` (case-insensitive).
- 24-slot hour histogram from event `created_at`.
- 52-slot weekly commit histogram from `contributions.weeks[].contributionDays[].contributionCount`.
- Streak: current = trailing consecutive non-zero days; longest = max run.
- Account age = `now - profile.created_at`.
- Activity span = last event time − first event time within the returned window.

### 6.3 score_v1 — formulas

Every stat: `clamp(round(f(signals)), 1, 20)`. Thresholds are absolute (PRD §open-questions: absolute).

| Stat | Formula sketch | Hits 12 at | Hits 18 at |
|---|---|---|---|
| **STR** | `log10(commits + pushes*2 + 1) * 6` | ~100 ops | ~1000 ops |
| **DEX** | `event_rate_per_day * 2 + current_streak_days / 30` | ~5 events/day | ~10/day + 60d streak |
| **CON** | `(activity_span_days / 30) + inverse_variance(weekly_commits) * 5` | 6mo steady | 12mo rock-steady |
| **INT** | `log2(distinct_repos_touched + 1) * 3 + gists` | ~8 repos | ~16 repos + several gists |
| **WIS** | `sqrt(account_age_days / 30) + review_ratio * 8` | ~5yr + healthy reviews | long-tenured, review-heavy |
| **CHA** | `distinct_external_repos_touched * 2 + (pr_reviews + issue_comments) / 4` | 5+ external repos, active commenter | frequent external collaborator |

Where `review_ratio = pr_reviews / max(prs_authored + commits_on_own, 1)`. This rewards reviewers over committers — seniority signal.

**LUCK** is cosmetic: `int(sha256(username.lower()).digest()[:2], "big") % 20 + 1`. Deterministic. Returned in the response; frontend chooses whether to render it.

Every Stat carries `raw_score` and `contributing_signals` so `/raw` can explain where a score came from. This doubles as an interview demo hook — "click a stat, see the math."

### 6.4 Versioning discipline

- `engine_version` is an integer, committed in source, bumped in one commit that adds `engine/vN/`.
- A new version **must** add a golden-file test for every existing fixture and its own new ones.
- `LATEST` is what new computations use. Historical snapshots remember whatever version they were computed with.
- Replay happens via `replay_service.recompute(raw_snapshot_id, engine_version)` and returns a fresh sheet without persisting.
- `GET /v1/engine/versions` → `{ latest: N, known: [1, 2, ...] }`.

### 6.5 Snapshot schema versioning

`raw_schema_version` is separate from `engine_version`. It bumps when the collector starts pulling new fields. Old raw snapshots may lack new fields; engine versions handle this explicitly (graceful default or `IncompatibleSnapshot` on replay). v0 ships at `raw_schema_version = 1`.

## 7. Collector

### 7.1 Client contract

```python
class GitHubClient:
    async def get_profile(self, username: str) -> GHProfile: ...
    async def get_public_events(self, username: str) -> list[GHEvent]: ...
    async def get_contributions(self, username: str) -> GHContributions: ...
    async def get_gists_meta(self, username: str) -> GHGistsMeta: ...
```

One client instance per process, shared via FastAPI dependency. Every method:

1. Builds a URL key (sha256 of URL + sorted query).
2. Reads `github_etag` cache from Redis for a stored `(etag, body)` pair.
3. Sends `If-None-Match: <etag>` when present.
4. On `304`, returns the cached body; metric label `cache="etag"` (still counts as success).
5. On `200`, updates Redis with the new etag + gzipped body.
6. On *any* response, parses `X-RateLimit-Remaining` + `X-RateLimit-Reset` and writes them to the Redis rate-limit gauge.

### 7.2 Pagination

- Events API returns up to 300 events across 10 pages. v0 fetches page 1 only (30 events). This keeps the rate-limit budget low and still covers the most recent signal. Deeper pagination is a Phase 2 config flag.
- Gists: fetch first page only; use `profile.public_gists` as the authoritative count.

### 7.3 GraphQL

One query for the contributions calendar:

```graphql
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
```

v0 uses the default 1-year window. GraphQL ETags are supported on POST — same cache path, keyed by `(query_hash, variables_hash)`.

### 7.4 Snapshot orchestration

```python
# collector/fetch.py
async def build_snapshot(username: str) -> RawSnapshot:
    profile, events, contributions, gists = await asyncio.gather(
        client.get_profile(username),
        client.get_public_events(username),
        client.get_contributions(username),
        client.get_gists_meta(username),
    )
    return RawSnapshot(...)
```

Partial snapshots are worse than no snapshot for a stats engine — any sub-call raising `GitHubUnavailable` fails the whole build.

### 7.5 Errors

```python
class GitHubError(Exception): ...
class UserNotFound(GitHubError): ...        # 404
class RateLimited(GitHubError): ...         # 403 + X-RateLimit-Remaining=0
class RateLimitFloorHit(GitHubError): ...   # circuit breaker: gauge < floor
class GitHubUnavailable(GitHubError): ...   # 5xx, network errors
```

API translates: `UserNotFound → 404`, `RateLimitFloorHit → 503` with `Retry-After`, everything else → `502`.

## 8. Cache design (Redis)

All keys under `lethargy:`.

| Purpose | Key | TTL | Value |
|---|---|---|---|
| GitHub ETag cache | `lethargy:gh:etag:<sha256(url+query)>` | 24h sliding | msgpack `{etag, body_gzip, stored_at}` |
| Sheet cache | `lethargy:sheet:<username>:<engine_version>` | `FRESH + STALE` | JSON of `CharacterSheet` |
| Refresh lock | `lethargy:lock:<username>` | 30s | owner token |
| Refresh throttle | `lethargy:throttle:<username>` | `REFRESH_THROTTLE_SECONDS` | empty sentinel |
| Rate-limit gauge | `lethargy:gh:ratelimit` | none | hash `{remaining, reset, updated_at}` |

### 8.1 Stale-while-revalidate

Each sheet cache entry carries a `computed_at`. Service logic:

1. `age < FRESH_TTL` → serve as-is, `X-Cache-Status: hit`.
2. `FRESH_TTL ≤ age < FRESH_TTL + STALE_TTL` → serve stale (`X-Cache-Status: stale`) and spawn a detached task to refresh. v0 traffic is low enough that a detached `asyncio.Task` on the running loop replaces a broker.
3. `age ≥ FRESH_TTL + STALE_TTL` → synchronous refresh before response.

### 8.2 Thundering herd

Before a synchronous refresh:
1. `SET lock:<username> NX EX 30`.
2. If acquired, proceed.
3. If not, poll every 250ms for up to 5s for a fresh cache entry. If one appears, serve it; otherwise `503` with a hint.

### 8.3 Throttle

Even when the cache would let us refresh, `throttle:<username>` stops us from hammering GitHub. If the throttle is armed **and** a cached sheet exists (even stale), serve cache with `X-Cache-Status: throttled`. If there's no cached sheet at all — first view for this user — bypass the throttle so the request can still complete.

## 9. Persistence (Postgres)

### 9.1 Schema

```sql
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE raw_snapshot (
  id                 BIGSERIAL PRIMARY KEY,
  username           CITEXT NOT NULL,
  fetched_at         TIMESTAMPTZ NOT NULL,
  raw_schema_version INTEGER NOT NULL,
  profile            JSONB NOT NULL,
  events             JSONB NOT NULL,
  contributions      JSONB NOT NULL,
  gists_meta         JSONB NOT NULL,
  UNIQUE (username, fetched_at)
);
CREATE INDEX raw_snapshot_user_time
  ON raw_snapshot (username, fetched_at DESC);

CREATE TABLE computed_sheet (
  id                 BIGSERIAL PRIMARY KEY,
  raw_snapshot_id    BIGINT NOT NULL REFERENCES raw_snapshot(id) ON DELETE CASCADE,
  username           CITEXT NOT NULL,
  engine_version     INTEGER NOT NULL,
  computed_at        TIMESTAMPTZ NOT NULL,
  signals            JSONB NOT NULL,
  stats              JSONB NOT NULL,
  flavor             JSONB NOT NULL,
  UNIQUE (raw_snapshot_id, engine_version)
);
CREATE INDEX computed_sheet_user_time
  ON computed_sheet (username, computed_at DESC);
```

Migrations via Alembic. `CITEXT` lets us store usernames case-insensitively without hand-rolled lowercasing everywhere.

### 9.2 Owner-only writes

The service layer gates writes so the rule is visible at the call site:

```python
async def persist_if_owner(username: str, snapshot: RawSnapshot, sheet: CharacterSheet):
    if username.lower() not in settings.owner_usernames_lower:
        return
    async with db.tx() as tx:
        raw_id = await snapshots.insert(tx, snapshot)
        await sheets.insert(tx, raw_id, sheet)
```

### 9.3 Replay on demand

```python
# services/replay_service.py
async def recompute(username, raw_snapshot_id, target_version):
    snap = await snapshots.get(raw_snapshot_id)
    if snap.username.lower() not in settings.owner_usernames_lower:
        raise NotAuthorized
    engine = ENGINES[target_version]
    signals = engine.extract(snap)
    sheet = engine.score(signals, snap.fetched_at)
    return sheet                                       # not persisted by default
```

`POST /v1/sheet/{username}/recompute?engine=N` is owner-only. When engine v2 lands, use it to backfill sheets for the history view.

## 10. Services layer

One class, `SheetService`. Its `get_or_refresh` is the blueprint for the whole hot path:

```python
async def get_or_refresh(self, username: str, force: bool = False) -> SheetEnvelope:
    username = username.lower()

    # 1. Cache read
    cached = await self.sheet_cache.get(username, engine=LATEST)

    if cached and not force and cached.age < self.settings.fresh_ttl:
        return SheetEnvelope(sheet=cached.sheet, status="hit")

    if cached and not force and cached.age < self.settings.fresh_ttl + self.settings.stale_ttl:
        self.tasks.spawn(self._refresh_background(username))
        return SheetEnvelope(sheet=cached.sheet, status="stale")

    # 2. Throttle (unless first view or forced)
    if not force and cached and await self.throttle.exists(username):
        return SheetEnvelope(sheet=cached.sheet, status="throttled")

    # 3. Synchronous refresh under a per-username lock
    async with self.locks.acquire_or_wait(
        username,
        fresh_cb=lambda: self.sheet_cache.get(username, LATEST),
    ) as outcome:
        if outcome.served_while_waiting:
            return SheetEnvelope(sheet=outcome.fresh_sheet, status="hit")

        await self.rate_limit.require_floor()

        snapshot = await self.collector.build_snapshot(username)
        engine = ENGINES[LATEST]
        signals = engine.extract(snapshot)
        sheet = engine.score(signals, snapshot.fetched_at)

        await self.sheet_cache.put(username, LATEST, sheet)
        await self.throttle.arm(username)

        if username in self.settings.owner_usernames_lower:
            await self.persist_if_owner(username, snapshot, sheet)

        return SheetEnvelope(sheet=sheet, status="miss")
```

Every `await` in this method is a span name — tracing is mechanical.

## 11. API surface

JSON responses. Correlation id in `X-Request-Id`. Engine headers on sheet responses.

### 11.1 Routes

| Method | Path | Purpose | Owner-only? |
|---|---|---|---|
| GET | `/v1/sheet/{username}` | Current character sheet | no |
| GET | `/v1/sheet/{username}/raw` | Signals + contributing inputs | no |
| GET | `/v1/sheet/{username}/history` | Past snapshots | yes (404 otherwise) |
| POST | `/v1/sheet/{username}/recompute?engine=N` | Replay against a specific engine | yes |
| GET | `/v1/engine/versions` | `{latest, known}` | no |
| GET | `/healthz` | Cheap liveness | no |
| GET | `/metrics` | Prometheus | no |
| GET | `/docs` | OpenAPI (FastAPI default) | no |

### 11.2 Response headers

- `X-Request-Id`
- `X-Engine-Version`
- `X-Raw-Schema-Version`
- `X-Cache-Status: hit | stale | miss | throttled`
- `X-Fetched-At` (ISO 8601)

### 11.3 Response body — GET /v1/sheet/{username}

```json
{
  "username": "octocat",
  "engine_version": 1,
  "raw_schema_version": 1,
  "fetched_at": "2026-04-14T12:34:56Z",
  "computed_at": "2026-04-14T12:34:56Z",
  "stats": {
    "STR": { "value": 14, "raw_score": 13.7, "inputs": {"commits": 420, "pushes": 117} },
    "DEX": { "value": 12, "raw_score": 11.6, "inputs": {"event_rate": 4.8, "current_streak_days": 23} },
    "CON": { "value": 10, "raw_score":  9.8, "inputs": {"activity_span_days": 180, "inverse_variance": 0.6} },
    "INT": { "value":  9, "raw_score":  9.0, "inputs": {"distinct_repos_touched": 7, "gists": 2} },
    "WIS": { "value": 15, "raw_score": 14.9, "inputs": {"account_age_days": 3150, "review_ratio": 0.42} },
    "CHA": { "value": 11, "raw_score": 11.2, "inputs": {"distinct_external_repos_touched": 4, "pr_reviews": 18} },
    "LUCK":{ "value":  7, "raw_score":  7.0, "inputs": {"hash": "deterministic"} }
  },
  "flavor": {
    "account_age_days": 3150,
    "hour_histogram": [0, 0, 0, ...],
    "current_streak_days": 23,
    "longest_streak_days": 91
  }
}
```

## 12. Observability

### 12.1 Spans

All names in `obs/names.py`:

```
api.sheet.get
api.sheet.raw
api.sheet.history
api.engine.versions
service.sheet.get_or_refresh
cache.sheet.get / put
cache.lock.acquire / release
cache.throttle.check / arm
collector.snapshot.build
collector.github.profile
collector.github.events
collector.github.contributions
collector.github.gists
engine.extract.v<N>
engine.score.v<N>
persistence.snapshot.insert
persistence.sheet.insert
```

Every span carries `engine.version`, `raw_schema_version`, `cache.status`, and `username.hash`. Raw usernames appear only on the root request span and only for **owner** usernames — a span processor strips `username` for non-owners before export.

### 12.2 Metrics (Prometheus)

Stable label sets — no unbounded cardinality.

```
http_requests_total{route, status}
http_request_duration_seconds{route}                       # histogram
sheet_cache_result_total{result}                           # hit|stale|miss|throttled
sheet_engine_compute_seconds{version}                      # histogram
collector_github_requests_total{endpoint, status, cache}   # cache=hit|miss|etag
collector_github_duration_seconds{endpoint}                # histogram
github_rate_limit_remaining                                # gauge
github_rate_limit_reset_seconds                            # gauge
owner_snapshots_total{username}                            # counter; cardinality bounded by config
engine_version_info{version}                               # gauge, set to 1 on startup
process_up
```

The only metric with a `username` label is `owner_snapshots_total`, and its cardinality is bounded by `LETHARGY_OWNER_USERNAMES`. No per-user panels in Grafana — confirmed in §16.

### 12.3 Logs

Structured JSON to stdout. Required fields:

```
ts level msg logger trace_id span_id
username_hash engine_version cache_status route
http_status duration_ms
```

**Raw usernames are never logged.** `username_hash = sha256(username.lower()).hexdigest()[:16]`.

Promtail ships container logs into Loki. Grafana explore uses `{service="api"}` as the base label.

### 12.4 Dashboards

One Grafana dashboard: **lethargy — SRE health**. Panels (pure ops, no user-level data):

1. HTTP p50 / p95 / p99 latency by route.
2. HTTP error rate by status class.
3. Sheet cache result ratio over time (`hit | stale | miss | throttled`).
4. GitHub rate-limit remaining (single-stat + time series).
5. GitHub call volume by endpoint, with etag / 304 overlay.
6. Engine compute time histogram by version.
7. Log volume over time, with error-level filter.

### 12.5 Alerts

One end-to-end alert proves the pipeline without turning alerting into its own project:

- **GitHubBudgetLow**: `github_rate_limit_remaining < 1000` for 5m → Slack webhook.

## 13. Config surface

Env vars, loaded once at startup into a frozen `Settings` dataclass. Never re-read at runtime.

| Var | Default | Notes |
|---|---|---|
| `LETHARGY_OWNER_USERNAMES` | `""` | Comma-separated, lowercased on load |
| `LETHARGY_GITHUB_TOKEN` | — | App token, required |
| `LETHARGY_DB_URL` | — | `postgresql+asyncpg://...` |
| `LETHARGY_REDIS_URL` | — | `redis://redis:6379/0` |
| `LETHARGY_SHEET_FRESH_TTL_SECONDS` | `600` | 10 min |
| `LETHARGY_SHEET_STALE_TTL_SECONDS` | `3000` | 50 min after fresh |
| `LETHARGY_REFRESH_THROTTLE_SECONDS` | `600` | Minimum gap between refreshes per username |
| `LETHARGY_RATE_LIMIT_FLOOR` | `500` | Refuse GH calls if remaining < this |
| `LETHARGY_OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | |
| `LETHARGY_LOG_LEVEL` | `INFO` | |
| `LETHARGY_ENV` | `dev` | `dev` / `prod` |

## 14. Test strategy

### 14.1 Engine (the core asset)

- Fixtures under `tests/engine/fixtures/` — handcrafted `RawSnapshot` JSON for scenarios: quiet user, active solo, heavy reviewer, long streak, new account, dormant veteran.
- For each fixture + engine version, a golden `CharacterSheet` JSON under `fixtures/golden/`.
- `pytest --regenerate-golden` opts into regeneration; any stat-math change forces a diff review.
- Property test: for *any* valid RawSnapshot, every stat is in `[1, 20]` and every `inputs` dict is JSON-serializable.

### 14.2 Collector

- HTTP recorded with `pytest-recording` (vcrpy). Cassettes committed. Tokens scrubbed on record.
- Unit test for ETag flow: first call hits origin, second call sends `If-None-Match` and returns cached body with `cache="etag"`.
- Unit test for rate-limit gauge update.
- Unit test for error translation.

### 14.3 Service

- In-memory fakes for every dependency (`SheetCache`, `Lock`, `Throttle`, `RateLimit`, `Collector`, `Persistence`).
- State table coverage: fresh hit, stale hit with background refresh, miss with lock acquired, miss with lock contended + waiter served, throttled, rate-limit floor, first-view bypass, owner-path persists, non-owner-path does not.
- No real Redis in service tests.

### 14.4 API

- FastAPI `TestClient` over a `SheetService` fed fake dependencies.
- Assert response shapes, headers, status codes.
- `/history` returns 404 for non-owner.

### 14.5 Persistence

- Real Postgres via `testcontainers-python` or a scratch compose. Round-trip a snapshot + sheet, assert unique constraints.

### 14.6 End-to-end smoke

- `docker compose up` + a single pytest that hits `/v1/sheet/<owner>` against a live container with a real token against your account. Gated behind `LETHARGY_E2E=1`. Run manually before each deploy.

## 15. Bootstrapping sequence

### Week 1 — walking skeleton
- `pyproject.toml` with core deps (`fastapi`, `uvicorn[standard]`, `httpx`, `redis`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `opentelemetry-*`, `pydantic`, `pytest`, `pytest-recording`, `msgpack`).
- `Dockerfile`, `docker-compose.yml` with api + postgres + redis.
- `config.py` + `.env.example`.
- `api/app.py` with `/healthz` and `/metrics`.
- `collector/client.py` with `get_profile` only, ETag + Redis caching wired.
- First integration: `GET /v1/sheet/{username}` returns `{"profile": ...}` pass-through.
- Alembic init + empty migration.
- OTel wiring: FastAPI instrumentation, httpx instrumentation, OTLP exporter.
- A Grafana dashboard, even if sparse.

### Week 2 — engine v1
- `engine/domain.py`, `engine/v1/{extract,score}.py`, `engine/registry.py`.
- Full collector: events + contributions + gists.
- First fixtures and golden files.
- `SheetService.get_or_refresh` minus cache/lock (naive pass-through) so end-to-end starts working.
- Alembic migration for `raw_snapshot` + `computed_sheet`.
- Owner-only persistence gate.

### Week 3 — production hardening
- Cache layer: sheet cache, lock, throttle, stale-while-revalidate.
- Rate-limit gauge + circuit breaker.
- All metrics + full dashboard.
- Loki + promtail in compose.
- `GitHubBudgetLow` alert → Slack.
- Deploy to VPS: Caddy + TLS, basic-auth Grafana, first real-world `/v1/sheet/<owner>` from the internet.

### Week 4 — frontend + polish
- Minimal Astro/htmx frontend that consumes the API.
- Portfolio links page (static).
- Share-link UX for non-owner usernames.
- Interview dry-run: walk through every layer with the live dashboard open. Iterate on rough edges you find while narrating.

## 16. Open design decisions (confirm or override)

1. **"Connected their github" interpretation.** v0 treats this as a single `LETHARGY_OWNER_USERNAMES` env var. Anyone else gets a stateless pass-through. If you want an actual opt-in flow in v0 (someone visits `/connect`, gets persistence for their own sheet), that's a different design and pushes OAuth work into v0 scope.
2. **Squash-merge attribution.** v0 dedupes push-event shas within the window but does not attempt to detect squash merges. PRD Phase 2 revisits.
3. **LUCK visibility.** Returned in every response. Frontend decides whether to render it. If you'd rather gate it server-side (owner-only), say so.
4. **Contribution calendar depth.** v0 requests the default 1 year. 5-year veterans get truncated history for WIS's weekly signal; account age still captures seniority via `profile.created_at`.
5. **`?force=1` query param.** Useful for demos: bypass cache + throttle. Owner-only, protected by the rate-limit floor. Say no if you want the hot path identical for everyone.
6. **Username hashing in logs.** `sha256(username.lower())[:16]`. Raw usernames appear only on the root request span and only for owners. Flag if this is too strict or too loose.
7. **Weekly histogram length.** 52 to align with GitHub's contribution calendar. If you prefer rolling 90 days, CON's formula shifts.
8. **Postgres vs Redis for ETag cache.** Blueprint puts ETag cache in Redis for speed and to keep "durable store = owner only." A Redis restart loses ETags and we re-consume rate-limit budget rebuilding them. Acceptable for v0 traffic; flag if not.
9. **Observability stack completeness.** Loki + promtail add two containers and a dashboard story. If you'd rather start with Prometheus + Grafana only and skip log aggregation, week 3 is simpler but the demo is weaker.
10. **Pagination depth.** v0 fetches events page 1 (30 events). Going to all 10 pages = 10× the rate-limit cost per refresh. Phase 2 config flag.
