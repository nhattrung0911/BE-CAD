# Final Platform Decisions

## Source folder decision

`final/` uses `fastener-cad-platform` as the base because it already has the production-grade backend shape: FastAPI, typed schemas, repository boundaries, Alembic, artifact storage, async generation jobs, vendor asset ingestion, and a working test suite.

`demo claude` contributed the frontend-facing geometry contract and cache philosophy: product variants, LOD-aware geometry hashes, immutable hash URLs, Redis/S3-style cache layering, and a clear Three.js integration flow.

## Production principles

- Do not scale one mesh to represent different SKUs.
- Vendor 3D assets are valid only for exact product, size, format, and license status.
- Parametric generation is the fallback for missing vendor assets.
- The product page should prefer cached GLB artifacts and should not block on heavy CAD generation.
- LOD is part of the geometry identity, so low, medium, and high viewer assets get distinct hashes.
- Hash URLs are immutable and CDN-friendly.
- `TEMPLATE_VERSION` is part of the hash; bump it when generator/export behavior changes so stale GLB/JSON artifacts cannot be served under old semantics.
- Worker queues are separated by workload: preview, CAD generation, engineering exports, and batch pregeneration.

## Backend boundaries

- API routes stay thin and call services.
- Product/variant catalog logic is isolated in `app.services.product_service`.
- Model resolution stays in `app.services.model_resolver`.
- Artifact persistence stays in `app.services.artifact_service`.
- Hashing stays deterministic through `app.services.hash_service`.
- Frontend-specific geometry routes adapt the product variant flow to the model resolver instead of bypassing it.

## Current implementation status

- Ready now:
  - product list and parameter schema
  - variant picker contract
  - geometry generate contract
  - geometry by variant contract
  - immutable hash URL serving
  - vendor asset ingestion
  - 2D metadata ingestion
  - async model job scaffolding
  - local storage plus S3-ready storage interface
  - Redis-ready cache interface with in-memory fallback

- Still intentionally isolated:
  - default local tests can use the deterministic mock backend for speed
  - real preview GLB is available through `CAD_BACKEND=cadquery` and CadQuery/OCC `Assembly.export("*.glb")`
  - engineering STEP/STL generation is available when `CAD_BACKEND=cadquery` and dependencies are installed
  - frontend demo is a contract consumer, not the final shop UI
