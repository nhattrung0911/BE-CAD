# Technical Report - Fastener CAD Demo

## Current scope

The project now has a production-oriented backend baseline plus a minimal frontend demo. The frontend is only a contract viewer; the real product UI can be built later by FE engineers.

## Backend architecture

- FastAPI backend exposes product, variant, geometry, artifact, job, ingestion, health, and readiness APIs.
- Product selection flow is explicit: product -> variant -> parameter set -> geometry hash -> GLB artifact.
- CadQuery/OCC generates real geometry for preview GLB when `CAD_BACKEND=cadquery`.
- GLB export uses CadQuery `Assembly.export("*.glb")`, so Three.js receives binary glTF instead of placeholder JSON.
- `TEMPLATE_VERSION=cadquery-glb-v1` is included in hashes to invalidate old artifacts after exporter changes.
- Artifacts are stored behind stable URLs and can be moved from local storage to S3/MinIO without changing API consumers.
- Resolver order remains scalable: cache/DB artifact -> exact vendor model -> parametric generation -> async job.
- `/ready` checks database and storage instead of returning a fake health result.
- CORS is enabled for local demo origins only.

## Verification

- Backend tests: `28 passed`.
- Frontend build: `npm run build` passes.
- Local demo API verified for 5 products.
- Fresh CadQuery GLB output verified by binary magic bytes: `glTF`.

## Remaining production work

- Move demo catalog from Python constants to database/admin-managed seed data.
- Add real auth/rate limiting before public exposure.
- Add observability for generation latency, cache hit rate, and job failure rate.
- Add more standards and precise ISO/DIN dimension tables.
