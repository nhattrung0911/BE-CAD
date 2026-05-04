# AGENTS.md — mecsu.vn Fastener CAD Platform
# Production Contract v2.0 | Repo: nhattrung0911/BE-CAD
# ─────────────────────────────────────────────────────────────────

## MISSION

Deliver a production-grade backend that:
- Serves immutable GLB geometry for every fastener SKU (bulong/đai ốc) on mecsu.vn
- Handles 10,000+ SKUs via deterministic parametric generation — never by hand-drawing
- Returns cached geometry in <10ms (Redis hit) and generated in <500ms (CadQuery)
- Exposes a clear API contract so any FE engineer can build a 3D viewer on top
- Is trivially scalable: add SKUs by inserting DB rows, not modifying code

## ARCHITECTURE BOUNDARIES — DO NOT CROSS

```
backend/app/api/          ← HTTP layer only. No business logic.
backend/app/schemas/      ← Pydantic contracts only. No logic.
backend/app/services/     ← Orchestration. Single source of truth.
backend/app/repositories/ ← DB access only. No business logic.
backend/app/db/           ← SQLAlchemy models only.
backend/app/cad/          ← CadQuery generators + template registry.
backend/app/workers/      ← Celery task wrappers only.
backend/app/core/         ← Config, DB init, security helpers.
backend/alembic/          ← Schema migrations. THE ONLY WAY to change schema.
frontend-demo/            ← Local dev viewer. Not production FE.
infra/                    ← Docker Compose, Nginx, Dockerfiles.
```

## RESOLVER WATERFALL — IMMUTABLE ORDER

```
Request arrives
  │
  ▼ 1. cache.get(cache_key)                    →  ~3ms  HIT → return
  │
  ▼ 2. ArtifactRepository.find_resolved_model   →  ~5ms  HIT → cache + return
  │
  ▼ 3. VendorAssetRepository.find_exact          →  ~5ms  HIT → cache + return
  │
  ▼ 4. cache.acquire_lock(lock_key, ttl=120s)    →  atomic SETNX
  │      FAIL (another process generating) → enqueue job → return job_id
  │      PASS → continue
  │
  ▼ 5. _may_generate_inline()
  │      False (production) → enqueue + dispatch → return job_id
  │      True  (local dev)  → CadQuery.generate() → persist → cache → return
  │
  └── finally: cache.release_lock()
```

## GOLDEN RULES — NEVER VIOLATE

1. Never scale one mesh to fake another SKU. Each combination = independent generation.
2. Never use AUTO_CREATE_SCHEMA=true in production. Alembic only.
3. Never silently fall back Redis → InMemory when REQUIRE_REDIS_FOR_READY=true.
4. Never run heavy CadQuery work in a production request path (queue it).
5. Never expose /ingest or /vendor-assets without admin API key guard.
6. Cache TTL must always be explicit — never call cache.set() without ttl_seconds.
7. Hash keys must be deterministic and stable across restarts.
8. Lock TTL must be ≥10× expected generation time (CadQuery ~400ms → lock 60s min).

## PRODUCTION ENV REQUIREMENTS

```env
ENVIRONMENT=production
CAD_BACKEND=cadquery
MODEL_SYNC_GENERATION=false
AUTO_CREATE_SCHEMA=false
REQUIRE_REDIS_FOR_READY=true
ADMIN_API_KEY=<32-char random>
CORS_ALLOW_ORIGINS=https://mecsu.vn,https://www.mecsu.vn
REDIS_URL=redis://:password@redis:6379/0
DATABASE_URL=postgresql+psycopg://user:pass@postgres:5432/mecsu_cad
```

Starting with any other values for the first four flags in production
must raise `ValueError` at app startup — not at request time.

## TESTING GATE

Every task must pass before the next begins:

```bash
cd backend
python -m pytest -q -p no:cacheprovider          # all tests green
python -m alembic upgrade head                    # migrations clean
```

For FE changes:
```bash
cd frontend-demo
npm install
npm run build                                     # no warnings
```

## KNOWN GAPS BEING FIXED IN THIS SPRINT

Tracked in tasks/T01–T14. Do not address gaps outside this list
without updating AGENTS.md and adding a test.
