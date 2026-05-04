# Codex Task Prompts

Use these prompts one at a time.

## Task 1: DB layer

Implement SQLAlchemy models for products, dimension_sets, vendor_3d_assets, model_jobs, model_artifacts. Add Alembic migrations. Keep the current API behavior. Add repository classes and tests. Do not implement CadQuery yet.

## Task 2: Redis lock

Add Redis cache adapter with in-memory fallback. Add lock API `acquire_lock(key, ttl)` and `release_lock`. Use it in `ModelResolver.resolve`. Add tests that two identical uncached requests only create one generation path.

## Task 3: Async job API

Add Celery/RQ. For uncached requests return `queued`. Add `/api/v1/model-jobs/{job_id}`. Add worker task that calls existing mock CAD generator. Keep dev sync mode behind `MODEL_SYNC_GENERATION=true`.

## Task 4: CadQuery exporter

Add `CAD_BACKEND=mock|cadquery`. Implement CadQuery exporter for hex bolt with simplified visual thread. Export STEP and GLB if CadQuery supports it in environment; otherwise keep STEP export plus a documented conversion interface. Add tests that mock still works in CI.

## Task 5: Vendor 3D ingestion

Add upload endpoint for vendor STEP/STL/GLB with product_id and params. Store raw asset, compute checksum, validate measured dimensions where possible, generate preview GLB or mark pending. Add exact-match priority in resolver.

## Task 6: Pregeneration CLI

Add CLI `python -m app.cli.pregenerate --top-skus data/top_skus.json --format glb`. It should enqueue jobs or sync-generate in dev. Add dry-run mode.
