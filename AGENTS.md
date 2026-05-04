# AGENTS.md - Fastener CAD Platform

This file is the operating guide for AI agents and engineers working in this repository. Treat it as the project contract.

## Mission

Build a production-ready backend foundation for fastener CAD delivery at catalog scale.

The platform must:

- prefer exact vendor 3D assets when licensed and validated;
- fall back to deterministic parametric CAD templates;
- use 2D drawings for metadata extraction and validation, not as the only 3D source;
- serve immutable GLB preview artifacts for the web;
- serve STEP/STL engineering artifacts through queued generation;
- keep product pages fast by using cached or pregenerated assets.

## Architecture Boundaries

Primary backend layout:

- `backend/app/api/`: FastAPI route layer only. Keep request/response concerns here.
- `backend/app/schemas/`: Pydantic contracts. Do not hide business logic in schemas.
- `backend/app/services/`: orchestration, resolver, health, cache, storage, jobs.
- `backend/app/repositories/`: SQLAlchemy persistence only.
- `backend/app/db/`: database models.
- `backend/app/cad/`: CAD backend interface, template registry, family templates.
- `backend/app/workers/`: Celery task wrappers and queue dispatch.
- `backend/alembic/`: schema migrations. Production schema changes must go here.
- `frontend-demo/`: thin API contract demo, not the production frontend.

Do not merge these boundaries for convenience. New work should fit one of these layers.

## Resolver Contract

The model resolver order is:

1. in-memory/Redis cache;
2. DB artifact lookup;
3. exact approved vendor asset;
4. parametric CAD generation;
5. queued async generation for heavy or production paths.

Rules:

- Validate `product_id` and required params before resolver work starts.
- Do not scale one mesh to fake another SKU.
- Vendor assets are valid only when product, format, license, and validation state match.
- Generated artifacts must use stable hash keys based on product, template version, quality, format, and params.
- Product page APIs must not block on heavy CAD generation.

## Production Configuration

Production must use:

```text
ENVIRONMENT=production
AUTO_CREATE_SCHEMA=false
REQUIRE_REDIS_FOR_READY=true
ADMIN_API_KEY=<secret from secret manager>
CORS_ALLOW_ORIGINS=<approved frontend/admin origins only>
MODEL_SYNC_GENERATION=false
```

Schema creation in production is Alembic-only:

```powershell
cd backend
python -m alembic upgrade head
```

Do not call `Base.metadata.create_all()` from production runtime paths.

## Security And Ingestion

Admin ingestion routes are not public APIs.

Rules:

- `POST /api/v1/vendor-assets` requires `X-Admin-API-Key` when `ADMIN_API_KEY` is configured.
- Uploaded filenames and storage key segments must be sanitized.
- Path traversal must be rejected before local/S3 writes.
- Allowed asset formats are `glb`, `step`, and `stl`.
- License status is one of `pending`, `approved`, `restricted`, `rejected`.
- Validation status is one of `pending`, `valid`, `invalid`.
- Upload size is capped by `MAX_UPLOAD_BYTES`.
- Never commit secrets, real customer data, generated storage artifacts, logs, DB files, or `node_modules`.

## Catalog Model

Persistent catalog truth now lives in database-backed master data tables:

- `catalog_products`
- `catalog_parameter_specs`
- `catalog_variants`

The demo seed still exists for local/dev fallback through `backend/app/services/demo_catalog.py`.

Operator flow:

```powershell
cd backend
python -m alembic upgrade head
python -m app.bootstrap.seed_catalog
```

In production, `/ready` must stay `503` with `"catalog": "empty"` until persistent catalog data exists.

For scale-up to tens of thousands of SKUs, extend this master-data model with:

- product family;
- standard;
- product;
- variant/SKU;
- dimension specs;
- material and surface data;
- source asset and source version;
- validation state.

Keep the API contract stable while moving catalog storage behind service/repository boundaries.

## Queues And Workers

Queue names:

- `preview_fast`: fast preview GLB work.
- `cad_generate`: general CAD generation.
- `engineering_step`: STEP/STL engineering artifacts.
- `batch_pregenerate`: top SKU pregeneration.

Production API instances should enqueue uncached work. Workers perform CPU-heavy CAD generation.

Do not run heavy CadQuery/OCC work inside public request paths except local development preview mode.

## Testing Gates

Before claiming work is ready:

```powershell
cd backend
python -m pytest -q -p no:cacheprovider
```

For frontend demo changes:

```powershell
cd frontend-demo
npm.cmd run build
```

For migration changes:

```powershell
cd backend
python -m alembic upgrade head
```

Add tests for every behavior change. Foundation risks should be covered in `backend/tests/test_foundation_hardening.py`.

## Coding Rules

- Keep changes scoped and boring.
- Prefer existing service/repository patterns.
- Add abstractions only when they protect a real boundary.
- Keep API contracts explicit.
- Fail invalid input before queueing or generating CAD.
- Preserve deterministic hashes and immutable artifact URLs.
- Do not weaken readiness checks for production convenience.
- Do not silently fall back from Redis to in-memory locks when `REQUIRE_REDIS_FOR_READY=true`.

## Known Intentional Gaps

These are planned scale-up areas, not permission to bypass current contracts:

- production frontend is not included;
- catalog import beyond the demo seed is not implemented yet;
- metrics are Prometheus-style text counters, but not a full labeled metrics stack yet;
- rate limiting is not implemented yet;
- auth is API-key based for admin ingestion and should later move to stronger RBAC/OIDC.

When addressing these gaps, keep backward-compatible API behavior unless a migration plan is documented.
