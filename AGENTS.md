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

The model resolver order (`app/services/model_resolver.py`) is:

1. in-memory/Redis cache;
2. DB artifact lookup (resolved-model unique on product+params_hash+format+quality);
3. **vendor-variant exact** (`vendor_assets.variant_id == request.variant_id`, **`license=approved` AND `validation=valid`** — pending files are intentionally invisible until admin reviews);
4. **vendor-product fallback** (`vendor_assets.variant_id IS NULL` for the same product+format, same approve+validate gate) — only used when no variant-specific override exists;
5. parametric CAD generation (inline only when `MODEL_SYNC_GENERATION=true` AND format=glb AND quality=preview);
6. queued async generation for heavy or production paths.

Resolver source labels emitted in the response:
- `cache` / `cache_db` — hit path
- `vendor_variant` — per-variant override
- `vendor_exact` — product-level vendor file
- `generated_parametric` — inline CadQuery output
- `queued_parametric` — Celery dispatch

Rules:

- Validate `product_id` and required params before resolver work starts.
- Do not scale one mesh to fake another SKU.
- Vendor assets are valid only when product, format, license, and validation state match. Per-variant overrides take priority over product-level files.
- `find_exact()` must filter `variant_id IS NULL` so a generic product file does not silently override unrelated variants.
- Generated artifacts must use stable hash keys based on product, template version, quality, format, and params.
- Product page APIs must not block on heavy CAD generation.
- The `ModelResolveRequest.variant_id` field is the only signal the resolver has to choose vendor-variant; route layers (`/geometry/variant/{id}`) must populate it.

## Production Configuration

Production must use:

```text
ENVIRONMENT=production
AUTO_CREATE_SCHEMA=false
REQUIRE_REDIS_FOR_READY=true
ADMIN_API_KEY=<secret from secret manager, MIN 32 chars — enforced by Settings validator>
JWT_SECRET=<secret from secret manager, MIN 32 chars — enforced>
ALLOW_FIRST_ADMIN_BOOTSTRAP=false
CORS_ALLOW_ORIGINS=<approved frontend/admin origins only — no `*`, no `null`; enforced>
MODEL_SYNC_GENERATION=false
CAD_BACKEND=cadquery
```

`Settings.validate_production_settings` (`app/core/config.py`) enforces all of the above
and rejects boot if any is violated. Do not weaken these checks.

Other tunables (have safe defaults, override per environment):

- `INLINE_LOCK_TTL_SECONDS` (default 60) — preview-path generation lock TTL.
- `QUEUED_LOCK_TTL_SECONDS` (default 600) — STEP/STL queued path TTL.
- `MAX_UPLOAD_BYTES` (default 100 MB) — caps vendor-asset and 2D drawing uploads.
- `MAX_DRAWING_CONTENT_CHARS` (default 2,000,000) — caps the JSON `content` field on `/ingest/2d`.

Schema creation in production is Alembic-only:

```powershell
cd backend
python -m alembic upgrade head
```

Do not call `Base.metadata.create_all()` from production runtime paths.

`app/bootstrap/database.py` exposes `HEAD_REVISION` (currently `20260510_0005`).
When you add a new alembic version, bump `HEAD_REVISION` so the bootstrap path
correctly stamps fresh DBs created via `auto_create_schema=true` in dev/test.

## Authentication And Roles

Two principal types share the same `AuthPrincipal` interface
(`app/core/auth.py`):

1. **JWT bearer** — issued by `POST /api/v1/auth/login`. Header:
   `Authorization: Bearer <token>`. Decoded into `(user, role)`. Tokens are
   HS256-signed with `JWT_SECRET`, default TTL 60 min.
2. **Machine admin key** — `X-Admin-API-Key` header matching
   `ADMIN_API_KEY`. Treated as `role=admin, is_machine=true`. Used by CLI
   scripts (`scripts/ingest_research_samples.py`, etc.) and CI.

Roles (`app/core/auth.py:VALID_ROLES`):

- `viewer`  — read vendor-asset metadata, read pending raw files
- `uploader` — upload vendor assets and 2D drawings; cannot self-approve
- `admin`   — review/approve files, create/promote users, read restricted

Role enforcement uses `Depends(require_role(*roles))` — admin always passes.
Use this pattern for any new admin/operator route.

**Bootstrap:** the first user is created either via the CLI
(`python -m app.bootstrap.create_admin --email a@b.com --password ...`) or
via `POST /api/v1/auth/register` while the users table is empty AND
`ALLOW_FIRST_ADMIN_BOOTSTRAP=true` (dev only — production validator blocks
this combination at boot).

**Dev open-mode:** when `ENVIRONMENT != production`, `ADMIN_API_KEY` is unset,
and `ALLOW_FIRST_ADMIN_BOOTSTRAP=true`, all admin/uploader routes accept
unauthenticated requests as a synthesized machine-admin. This keeps
local dev frictionless and is forbidden by the production validator.

**Audit:** every state-changing auth/upload/review action writes an
`audit_log` row via `app/services/audit_service.py:record_audit`. Failure to
write the audit row MUST be logged but MUST NOT break the request.

## Security And Ingestion

Admin ingestion routes are not public APIs.

Rules:

- `POST /api/v1/vendor-assets` requires role `uploader` or `admin` (or
  machine `X-Admin-API-Key`). Non-admin uploaders cannot self-approve:
  the server forces `license_status=pending, validation_status=pending`
  for them and persists `uploaded_by_user_id`.
- `PATCH /api/v1/vendor-assets/{id}/status` requires role `admin` and
  records `reviewed_by_user_id`.
- `POST /api/v1/ingest/2d` and `/ingest/2d/upload` require role `uploader`
  or `admin` (or machine key).
- `GET {public_raw_asset_prefix}/{key}` is served by the gated route
  `app/api/routes_raw_assets.py` — never by `StaticFiles`. License/validation
  matrix:
  - `approved + valid` → public, `Cache-Control: public, max-age=86400`
  - `approved + pending` → any authenticated role
  - `restricted` / `rejected` / `validation=invalid` → admin only;
    anonymous probes get `404` to avoid existence disclosure
- Generated artifacts (`{public_artifact_prefix}/...`) remain a public
  StaticFiles mount — they are content-addressed by stable hash and contain
  no licensed third-party data.
- Rate limits (`app/core/rate_limit.py`) — sliding window, Redis-backed if `REDIS_URL` set, in-memory fallback. Apply via `Depends(rate_limit(name=..., limit=..., window_seconds=...))`:
  - `/ingest/2d*` — 30 hits/min per (admin key prefix or IP).
  - `/vendor-assets POST` — 20/min.
  - `/vendor-assets GET/PATCH` — 60/min.
  - `/auth/login` — 10/min; `/auth/register` — 20 per 5 min.
  - `/geometry/generate`, `/geometry/variant/*`, `/models/resolve` — public
    rate-limited at `PUBLIC_GEOMETRY_RATE_LIMIT` (default 60/hour) per IP.
  - In-memory limiter only protects a single replica; Redis is required for multi-replica production.
- Uploaded filenames and storage key segments must be sanitized via `safe_storage_segment`.
- Path traversal must be rejected before local/S3 writes.
- `product_id` and `variant_id` fields must match `[A-Za-z0-9._-]+` (enforced in schemas and routes).
- Allowed asset formats are `glb`, `step`, and `stl`. Allowed 2D drawing extensions are `svg` and `txt`.
- License status is one of `pending`, `approved`, `restricted`, `rejected`.
- Validation status is one of `pending`, `valid`, `invalid`.
- The vendor-asset table has an optional `variant_id` column (migration `20260505_0004`) plus `uploaded_by_user_id` / `reviewed_by_user_id` columns (migration `20260510_0005`). Per-variant uploads nest under `<product_id>/<format>/<variant_id>/<filename>` to avoid collision with product-level uploads.
- Upload size is capped by `MAX_UPLOAD_BYTES`. JSON drawing content also capped by `MAX_DRAWING_CONTENT_CHARS`.
- Never commit secrets, real customer data, generated storage artifacts, logs, DB files, vendor reference files, or `node_modules`.

**Vendor reference files (research only):** `backend/storage/research-samples/` is gitignored and intended for vendor STEP/GLB downloads used only for parametric template validation (`scripts/analyze_samples.py --compare`). Files here MUST NOT be committed, redistributed, or served from a public endpoint. Use `scripts/ingest_research_samples.py` to load them into `vendor_assets` for local resolver testing only.

## Catalog Model

Persistent catalog truth lives in database-backed master data tables:

- `catalog_products`
- `catalog_parameter_specs`
- `catalog_variants`

Demo seed (`app/services/demo_catalog.py`) carries 9 products across 4 families:

| Family | Standards | Notes |
|---|---|---|
| `hex_bolt` | ISO 4014, DIN 931, DIN 933 | DIN 933 = fully threaded |
| `hex_nut` | ISO 4032, ISO 4033 | ISO 4033 = high nut |
| `washer` | ISO 7089, DIN 125 | |
| `retaining_ring` | GB 891 | |
| `button_head` | ISO 7380 | Domed head + hex socket cap |

Adding a new product:
1. Add a `Product(...)` entry in `app/services/demo_catalog.py` `CATALOG`.
2. Add `VARIANTS["<product_id>"] = [...]`.
3. If a new family is needed, add a `CadTemplate` subclass under `app/cad/templates/`, register it in `app/cad/registry.py`, and implement the geometry in `CadQueryBackend.<family_method>` in `app/cad/backends.py`.
4. Update the `seeded == N` and `len(products) == N` assertions in `tests/test_catalog_database_mode.py`.

Operator flows (two paths, both supported):

**Demo seed (dev only):**
```powershell
cd backend
python -m alembic upgrade head
python -m app.bootstrap.seed_catalog
```

**CSV bulk import (production-grade — operator-friendly, no code required):**
```powershell
python -m app.bootstrap.import_catalog --csv path/to/catalog.csv --dry-run
python -m app.bootstrap.import_catalog --csv path/to/catalog.csv
```

CSV headers: `product_id,family,standard,name,variant_id,sku,label,diameter_label,material,params` where `params` is a JSON object. The importer validates `product_id`/`variant_id` regex, checks param values are numeric, and prints per-row errors before any DB writes. ParameterSpec is auto-derived from the union of `params` keys per product.

In production, `/ready` must stay `503` with `"catalog": "empty"` until persistent catalog data exists.

For scale-up to tens of thousands of SKUs, the master-data model is sufficient as-is — the bottleneck is operator workflow (CSV importer covers it) and storage lifecycle (S3 lifecycle rule, ops task).

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

## CadQuery Generation Notes

The CadQuery backend (`app/cad/backends.py`) is a process-wide singleton via
`functools.lru_cache(maxsize=4)` on `_build_cad_backend(name)`. Tests that
monkeypatch `sys.modules["cadquery"]` MUST call `reset_cad_backend_cache()` —
the autouse fixture in `tests/conftest.py` already does this between cases.

**Threaded shank generation** (`_build_threaded_shank`):
- Builds a solid core cylinder at `minor_r` and unions with an outer ringed
  sleeve made by revolving a sawtooth-radius profile.
- The polyline must NOT include points at `radius=0` (axis). Points on the
  rotation axis cause OCC to emit a degenerate face that surfaces in the GLB
  as a giant flat disc.
- `Workplane("XZ").polyline(...).close().revolve(360, axisStart=(0,0,0), axisEnd=(0,1,0))` —
  note `axisEnd=(0,1,0)` because workplane local `y` maps to world `Z` for the
  `XZ` plane. `axisEnd=(0,0,1)` would revolve around world `Y` (silently
  produces wrong geometry).

**Internal nut threads** (`_hex_nut`):
- Cuts a threaded plug from the bore using the same `_build_threaded_shank`
  helper. Pitch is auto-resolved from `_coarse_pitch_for_diameter(d)` (ISO 261
  coarse-thread table). If `d` does not match within ±15% / ±2mm, falls back
  to a smooth cylindrical bore.

**End-cap chamfer / fillet** can fail on some param combinations (CadQuery
returns `OCC.StdFail.NotDone`). All chamfer/fillet calls are wrapped with
`try/except` that logs `logger.warning` and proceeds with un-chamfered
geometry. Do not silence these — the warning is what surfaces parameter
combinations that need template tuning.

## Coding Rules

- Keep changes scoped and boring.
- Prefer existing service/repository patterns.
- Add abstractions only when they protect a real boundary.
- Keep API contracts explicit.
- Fail invalid input before queueing or generating CAD.
- Preserve deterministic hashes and immutable artifact URLs.
- Do not weaken readiness checks for production convenience.
- Do not silently fall back from Redis to in-memory locks when `REQUIRE_REDIS_FOR_READY=true`.
- Do not use bare `except Exception: pass`. Log via the module's logger.
- When adding columns to existing tables, write the alembic migration AND bump `HEAD_REVISION` in `app/bootstrap/database.py`.
- When changing `_build_threaded_shank` or any `revolve()` call, verify the GLB bbox is sane (`scripts/analyze_samples.py` against a generated artifact, or check `accessor.min/max` directly). Past regressions produced 50mm+ wide ghost discs from axis-touching wires.
- Filename safety: any user-supplied or vendor filename that may include unicode (e.g., `Φ`) must go through `safe_storage_segment`; CLI scripts that print such filenames on Windows need `_safe_print` (cp1252 console).
- User-visible unicode in `frontend-demo/src/App.jsx` should use `\uXXXX` escapes, not raw chars, to avoid mojibake in tools that decode UTF-8 as cp1252.

## Test status

Current suite: **100/100 pass** (`python -m pytest -q -p no:cacheprovider`).
New behaviors should land with tests in:

- `tests/test_foundation_hardening.py` — security, config, ingestion guards.
- `tests/test_production_hardening.py` — rate limit, vendor variant override, CSV import, new templates.
- `tests/test_cad_backends.py` — CadQuery exporters and backend selection.
- `tests/test_catalog_database_mode.py` — DB-mode catalog repository, query bound counts.
- `tests/test_auth_rbac.py` — JWT + RBAC enforcement, machine-key fallback, audit log.
- `tests/test_raw_asset_gating.py` — license/validation gating on raw vendor downloads.

## Known Intentional Gaps

These are remaining scale-up / ops items, not permission to bypass current contracts:

- production frontend is not included; `frontend-demo/` is a thin contract consumer with `frameloop="always"`, no PWA, no SSR.
- structured JSON logging with request-id correlation is partial (request_id middleware sets header, but log output is plain text).
- SQLAlchemy connection pool is at SQLA defaults; no `pool_size` / `max_overflow` env tuning yet.
- metrics are Prometheus-style text counters; no full labeled metrics stack.
- auth uses local password + JWT (HS256, stdlib PBKDF2). OIDC / SSO / refresh-token rotation / MFA are not implemented yet — fine for an internal tool, must be revisited before exposing operator self-service to external customers.
- Celery dead-letter queue + alerting is not configured.
- vendor-asset upload accepts `variant_id` in the form, but the FE demo `Drawings` tab does not surface a variant picker yet (admins use `curl` or `scripts/ingest_research_samples.py`).
- secret vault integration (AWS Secrets Manager / Vault) is out of scope for this repo — production deployers must wire `ADMIN_API_KEY`, DB password, S3 credentials from a secret store, not env files.
- S3 lifecycle policy (artifacts retention) is an ops task, not codebase config.

When addressing these gaps, keep backward-compatible API behavior unless a migration plan is documented.

## Closed Gaps (do not re-open as TODO)

The following were listed as gaps in earlier revisions and are now done:

- ✅ Catalog import beyond demo seed → `app/bootstrap/import_catalog.py` (CSV).
- ✅ Rate limiting → `app/core/rate_limit.py` (sliding window, Redis or memory).
- ✅ CAD backend re-instantiation per request → `lru_cache` singleton.
- ✅ Lock TTL hardcoded → `INLINE_LOCK_TTL_SECONDS` / `QUEUED_LOCK_TTL_SECONDS`.
- ✅ Vendor file binding to product only → `vendor_assets.variant_id` column + variant-first resolver order.
- ✅ Production env validator missing key-strength / CORS-strict checks → enforced.
- ✅ Three new standards (DIN 933, ISO 4033, ISO 7380) added with seeded variants.
- ✅ Single shared admin key for all operators → multi-user auth + RBAC (`viewer/uploader/admin`) with JWT (`app/core/auth.py`, `app/api/routes_auth.py`); machine key kept as fallback for CLI.
- ✅ Vendor file leak via raw `StaticFiles` mount → gated `routes_raw_assets.py` enforces license/validation matrix; resolver tightened to `validation=valid` only.
- ✅ No audit trail → `audit_log` table + `audit_service.record_audit` writes on auth, upload, review, ingestion.
- ✅ Public `/geometry/generate` could be abused → IP rate limit (`PUBLIC_GEOMETRY_RATE_LIMIT`, default 60/h).
- ✅ CORS missing PATCH (preflight failures on vendor-asset review) → allowed.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **BE-CAD** (1020 symbols, 2505 relationships, 76 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/BE-CAD/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/BE-CAD/context` | Codebase overview, check index freshness |
| `gitnexus://repo/BE-CAD/clusters` | All functional areas |
| `gitnexus://repo/BE-CAD/processes` | All execution flows |
| `gitnexus://repo/BE-CAD/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## CLI

- Re-index: `npx gitnexus analyze`
- Check freshness: `npx gitnexus status`
- Generate docs: `npx gitnexus wiki`

<!-- gitnexus:end -->
