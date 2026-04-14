# lethargy.io — Product Requirements (v0)

## Summary
A public service that turns any GitHub username into a "character sheet" computed from their public activity. Output is deterministic, versioned, and served via a stable JSON API. A thin web frontend renders the sheet, but the system is API-first and frontend-agnostic.

The real product is the pipeline: GitHub data ingestion, a stat inference engine, a cache layer, persistence, and a full observability stack. The character sheet is the user-visible artifact; the implementation is the portfolio piece.

## Primary user
Single author using the site as an interview talking point. Secondary: anyone who wants to plug in their GitHub handle and see their own sheet. No auth in v0 — all inputs are already public.

## Non-goals (v0)
- No repo content analysis (Terraform detection, test coverage, Dockerfiles, language proficiency). Phase 2.
- No OAuth, no private data, no org repos. Ever, unless a user explicitly opts in later.
- No blog, CMS, or themed marketing copy.
- No recruiter optimization. Assume the reader is a technical interviewer who will ask "how does this work."
- No user accounts, saved profiles, or user-generated content.

## Success criteria
1. Any visitor can enter a GitHub username and see a character sheet in ~2s on a cache hit, ~5s on a miss.
2. The author can open the site in an interview, explain every layer of the stack, and point at a live Grafana dashboard showing the request in flight.
3. Stat inference is deterministic and versioned — same inputs, same stats, and old snapshots can be replayed against new engine versions.
4. The frontend can be replaced entirely without touching the API.
5. GitHub API quota is never exhausted under normal traffic — caching and conditional requests (ETag) are correctly wired.

## Scope — v0 stats (public activity only)
Data sources, unauthenticated or via a single app token for rate-limit headroom:
- `GET /users/{user}` — profile, account age, followers/following, public repo count, bio
- `GET /users/{user}/events/public` — up to 300 recent public events (~90 days)
- GraphQL `user.contributionsCollection` — commit/PR/issue/review counts, contribution calendar, restricted contribution count
- `GET /users/{user}/gists` — public gist count and recency

Event types parsed:
PushEvent, PullRequestEvent, PullRequestReviewEvent, PullRequestReviewCommentEvent, IssuesEvent, IssueCommentEvent, CreateEvent, ForkEvent, ReleaseEvent, WatchEvent, PublicEvent.

Derived signals:
- Account age and activity span (first-to-last event window)
- Contribution streak (current + longest)
- Commit volume, PR authorship, review count, issue participation
- Ratio of activity on own repos vs. others' repos (collaboration signal)
- Active repo diversity (distinct repos touched in window)
- Circadian profile (hour-of-day histogram) — flavor, not scored
- Consistency (variance of weekly activity)

## Stat model v1
Six visible stats, 1–20 scale, backed by raw scores that are logged and replayable:

| Stat | Signal | Rationale |
|---|---|---|
| STR | raw commit/push volume over window | output |
| DEX | event frequency + streak length | cadence, not bursts |
| CON | activity span + low variance across weeks | sustained presence |
| INT | distinct-repo diversity + gist count | breadth |
| WIS | account age + review:commit ratio | reviews weigh heavier than writes |
| CHA | PRs/reviews/comments on *other* users' repos | collaboration outside your own sandbox |

Each stat is a pure function: `(snapshot, engine_version) → score`. Engine version is stored with every snapshot so sheets can be recomputed.

A hidden LUCK stat is deterministic per username (hash-based) — cosmetic only.

## Architecture

```
  browser / API client
           │
           ▼
   ┌──────────────┐
   │ FastAPI app  │ ← OpenAPI docs, /healthz, /metrics
   └──────┬───────┘
          │
   ┌──────▼───────┐   hit/miss
   │ cache layer  │◄──────── Redis
   │ (ETag-aware) │
   └──────┬───────┘
          │ miss
   ┌──────▼───────┐
   │  collector   │ → GitHub REST + GraphQL
   └──────┬───────┘
          │
   ┌──────▼───────┐
   │ stat engine  │ pure, versioned
   └──────┬───────┘
          │
   ┌──────▼───────┐
   │  Postgres    │ raw snapshots + computed sheets
   └──────────────┘
```

**Choices (open to revisit):**
- **Backend:** Python + FastAPI — fast to ship, first-class OpenAPI, async HTTP for parallel GitHub calls, strong OTel/Prometheus ecosystem.
- **Persistence:** Postgres. Raw GitHub snapshots (JSONB), computed sheets keyed by `(username, engine_version, fetched_at)`, small audit log. History enables time-series charts and engine-version replays.
- **Cache:** Redis. Per-endpoint TTLs plus stale-while-revalidate so page loads stay fast while a background task refreshes.
- **Refresh model:** on page view, return cached sheet if younger than N minutes; else trigger refresh (low traffic so synchronous is fine). Background daily job warms common users.
- **Frontend:** Minimal — Astro or plain HTML+htmx rendering the JSON sheet. Disposable. The real UI is the OpenAPI docs page + Grafana.
- **Deploy:** Docker Compose on a single VPS for v0. k8s only if it becomes an honest part of the story, not a flex.

## Observability (first-class — half the point)

- **Tracing:** OpenTelemetry spans covering request → cache → GitHub → engine → DB. Export to Tempo or an OTel collector.
- **Metrics:** Prometheus endpoint. Counters for requests, cache hits/misses, GitHub calls by endpoint; gauges for rate-limit remaining; histograms for stat-engine compute time.
- **Logs:** Structured JSON to stdout, aggregated via Loki. Correlation IDs linking log lines to trace IDs.
- **Dashboards:** a Grafana dashboard that tells the story in an interview:
  1. Request latency p50/p95/p99
  2. Cache hit ratio
  3. GitHub rate-limit budget remaining
  4. Stat engine version in use + sheets computed per version
  5. Top requested usernames
- **Alerts:** at least one meaningful, routable alert — e.g., rate-limit budget < 20% or error-rate spike, wired to a demoable Slack webhook.

## GitHub rate-limit strategy
- Single app token, 5000 req/hr authenticated.
- ETag conditional requests on every REST GET — 304s don't consume budget.
- Redis response cache with per-endpoint TTLs.
- Per-username refresh throttle (≤1 refresh per 10 min regardless of views).
- Budget gauge + circuit breaker at a safe floor.

## API surface (v0)
- `GET /v1/sheet/{username}` — full computed character sheet
- `GET /v1/sheet/{username}/raw` — underlying raw signals (debugging + demo)
- `GET /v1/sheet/{username}/history` — prior snapshots
- `GET /v1/engine/versions` — known stat engine versions
- `GET /healthz`, `GET /metrics`, `GET /docs`

Every response includes `engine_version`, `fetched_at`, and `cache_status` headers.

## Milestones (~4 weeks)

**Week 1 — walking skeleton**
- FastAPI app, `/healthz`, `/metrics`, Docker Compose with Postgres + Redis
- GitHub client wrapper with ETag support
- First endpoint returning raw events, no stats yet
- OTel wiring, structured logs, basic Grafana dashboard

**Week 2 — stat engine v1**
- Signal extractors per event type
- Six stats as pure, versioned functions
- Snapshot persistence
- History endpoint

**Week 3 — production hardening**
- Cache with stale-while-revalidate
- Rate-limit gauge + circuit breaker
- Demo-ready Grafana dashboards
- One alert end-to-end
- Public VPS deploy behind TLS

**Week 4 — frontend + polish**
- Thin Astro/htmx frontend rendering the sheet
- Link-out portfolio section
- Share-link for any username
- Rehearse the interview narrative — literally talk through each layer

## Phase 2 (not now)
- Repo content analysis → Infra / Testing / Docs stats
- "Quest" per-repo scoring
- Opt-in OAuth for private contribution counts (never repo contents)
- Multi-frontend showcase (CLI, Slack bot, TUI) proving the API-first claim
- Social features — leaderboards, follows

## Open questions
1. **Engine version migration:** recompute history on v1→v2, or recompute on demand? (Lean: keep raw, recompute on demand.)
recompute on demand.
2. **Stat ceiling:** percentile-normalize across all computed sheets, or fix absolute thresholds? v0: absolute, revisit if it feels wrong.
absolute. 
3. **Squash merges + bot accounts:** squash-merged PRs attribute commits to the merger. Filter or ignore? v0: ignore, revisit in Phase 2.
ignore, revisit. 
4. **Privacy / opt-out:** anyone with a GitHub handle is lookup-able. Need a removal request path and a deny list.
no data will be saved if a user has not connected their github. no removal request needed. and lookups are snapshots in time. If i need to remove logs that are connected to a user we can add the removal request and deny list later. this is just for me in v0.
5. **Interview demo page:** host a "how this works" page on the site, or keep the talk track offline? Lean: offline track + live Grafana.
v0 keep it offline. grafana will just be site health and metrics. 
