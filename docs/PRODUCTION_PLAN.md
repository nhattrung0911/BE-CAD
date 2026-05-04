# End-to-End Production Plan

## Phase 0: Scope

- Confirm rights for vendor 2D/3D downloads.
- Select first standards: ISO4014, DIN934, GB891 or business-priority list.
- Define top SKU list for pregeneration.
- Confirm target file formats available from GlobalFastener.

## Phase 1: Technical POC

- Implement exact vendor 3D import path.
- Implement 2 templates: hex bolt + washer/retaining ring.
- Export GLB preview + STEP engineering.
- Add `param_hash` deterministic cache key.
- Add API contract tests.

Acceptance:
- cached GLB lookup under 200 ms locally;
- uncached mock generation deterministic;
- artifact URL stable by hash.

## Phase 2: Backend MVP

- PostgreSQL models and Alembic migrations.
- Redis cache/lock.
- Celery/RQ workers with separate queues:
  - preview_fast
  - cad_generate
  - engineering_step
  - batch_pregenerate
- S3/MinIO artifact storage.
- Admin ingestion endpoint for SVG/STEP/STL/GLB.
- Dimension validator.

## Phase 3: Production Hardening

- Runtime schema creation disabled with `AUTO_CREATE_SCHEMA=false`; database changes are applied only through Alembic migrations.
- Admin ingestion endpoints protected by `ADMIN_API_KEY` and the `X-Admin-API-Key` header.
- Storage keys sanitized before local/S3 writes; uploaded filenames and product identifiers must never be trusted as paths.
- `/ready` can require Redis by setting `REQUIRE_REDIS_FOR_READY=true`; multi-instance deployments must not silently fall back to in-memory locks.
- Worker autoscaling based on queue length.
- CDN immutable caching.
- GLB compression pipeline.
- Rate limit.
- Observability: request latency, request count, cache hit rate, job duration, failure rate.
- Backups and rollback.

## Production foundation gates

Before a team builds production features on this baseline:

- `python -m pytest -q -p no:cacheprovider` must pass.
- `PYTHONPATH=. alembic upgrade head` must be the only schema creation path in production.
- `AUTO_CREATE_SCHEMA=false`, `ADMIN_API_KEY` set to a secret value, and `REQUIRE_REDIS_FOR_READY=true` for scaled API deployments.
- Public product/geometry APIs and admin ingestion APIs stay separated by auth and audit policy.
- Catalog parameters must be validated before model generation; invalid products or missing dimensions must fail before queueing work.

## Performance policy

The product page must not wait for CAD generation. It should load metadata + 2D/thumbnail first, then request cached GLB. Missing models are generated async.
