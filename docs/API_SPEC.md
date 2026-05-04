# Backend API Contract

Base URL:

```text
/api/v1
```

## Health

```http
GET /health
```

## Products

```http
GET /api/v1/products
GET /api/v1/products/{product_id}
GET /api/v1/products/{product_id}/parameters
GET /api/v1/products/{product_id}/variants
```

`GET /api/v1/products/{product_id}/variants` is the main endpoint for the product-size picker. It returns variants grouped by nominal diameter:

```json
{
  "product_id": "hex-bolt-iso4014",
  "total": 4,
  "grouped_by_diameter": {
    "M8": [
      {
        "variant_id": "hex-bolt-iso4014-m8x30",
        "sku": "HEX-BOLT-ISO4014-M8X30",
        "label": "M8 x 30 mm",
        "params": {"d": 8, "L": 30, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
        "geometry": {
          "low_hash": "...",
          "medium_hash": "...",
          "high_hash": "..."
        }
      }
    ]
  }
}
```

## Frontend geometry contract

```http
GET /api/v1/geometry/variant/{variant_id}?lod=low|medium|high
POST /api/v1/geometry/generate
GET /api/v1/geometry/hash/{hash}
```

`GET /api/v1/geometry/variant/{variant_id}` resolves a selected catalog variant into a ready GLB artifact or a queued generation job:

```json
{
  "status": "ready",
  "hash": "a stable content hash",
  "hash_url": "/api/v1/geometry/hash/a-stable-content-hash",
  "variant_id": "hex-bolt-iso4014-m8x30",
  "lod": "medium",
  "product_id": "hex-bolt-iso4014",
  "params": {"d": 8, "L": 30, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
  "artifact": {
    "format": "glb",
    "quality": "preview",
    "url": "/artifacts/hex-bolt-iso4014/v0/.../preview.glb",
    "sha256": "...",
    "file_size": 1234
  },
  "cache": "miss",
  "source": "generated_parametric"
}
```

`GET /api/v1/geometry/hash/{hash}` serves immutable GLB bytes and sets:

```http
Cache-Control: public, max-age=31536000, immutable
Content-Type: model/gltf-binary
```

## Model resolve

```http
POST /api/v1/models/resolve
```

Request:

```json
{
  "product_id": "hex-bolt-iso4014",
  "params": {"d": 6, "L": 30, "P": 1, "k": 4, "s": 10, "b": 18},
  "format": "glb",
  "quality": "preview"
}
```

Response, cache hit or synchronous dev generation:

```json
{
  "status": "ready",
  "artifact": {
    "format": "glb",
    "quality": "preview",
    "url": "/artifacts/model_abcd.glb",
    "sha256": "...",
    "file_size": 1234
  },
  "cache": "hit",
  "source": "generated_parametric"
}
```

Production should return `202 queued` for uncached heavy CAD jobs.
# API Additions

## Health and operations

- `GET /health` returns process status, environment, and CAD backend.
- `GET /ready` executes database and storage checks. It returns `200` with `status: ready` only when all checks are healthy, otherwise `503` with `status: not_ready`.
- `GET /metrics` returns placeholder counters for future Prometheus integration.

## Model resolver

`POST /api/v1/models/resolve` remains backward compatible. It returns `ready` for cached artifacts, exact vendor assets, and mock preview generation; it returns `queued` for heavy engineering generation when no cached/vendor artifact exists.

Requests are validated against the catalog before resolver work starts:

- unknown `product_id` returns `404 Product not found`;
- missing required dimensions returns `400` with an `Invalid product parameters` detail payload;
- invalid format or quality is rejected by the request schema.

Resolver source values:

- `cache`
- `cache_db`
- `vendor_exact`
- `generated_parametric`
- `queued_parametric`

When `MODEL_SYNC_GENERATION=false`, uncached parametric requests return:

```json
{
  "status": "queued",
  "cache": "miss",
  "source": "queued_parametric",
  "job_id": "job_preview_fast_b92d51af306ac77aa9bc6f86"
}
```

## Model jobs

```http
GET /api/v1/model-jobs/{job_id}
```

Response:

```json
{
  "job_id": "job_preview_fast_b92d51af306ac77aa9bc6f86",
  "queue_name": "preview_fast",
  "status": "pending",
  "product_id": "hex-bolt-iso4014",
  "format": "glb",
  "quality": "preview",
  "artifact": null,
  "error_message": null
}
```

Job statuses are `pending`, `running`, `done`, and `failed`. When `done`, `artifact` contains the same artifact payload shape returned by `/models/resolve`.

## Vendor assets

`POST /api/v1/vendor-assets` accepts multipart form data:

When `ADMIN_API_KEY` is configured, callers must send:

```http
X-Admin-API-Key: <admin key>
```

- `product_id`
- `format`: `glb`, `step`, or `stl`
- `license_status`: `pending`, `approved`, `restricted`, or `rejected`
- `validation_status`: `pending`, `valid`, or `invalid`
- `file`

The response includes raw storage key, public URL, checksum, file size, license status, and validation status.

Uploaded filenames and storage key segments are sanitized before writing to local storage or S3. Path traversal segments are rejected.

Upload validation is enforced before storage writes:

- `format` must be `glb`, `step`, or `stl`;
- `license_status` must be `pending`, `approved`, `restricted`, or `rejected`;
- `validation_status` must be `pending`, `valid`, or `invalid`;
- file size must be less than or equal to `MAX_UPLOAD_BYTES`.

## 2D ingestion

`POST /api/v1/ingest/2d` accepts:

```json
{"product_id":"retaining-ring-gb891","content":"<svg><text>h:6.8-7.2</text></svg>"}
```

It extracts dimension ranges plus metadata keys: `unit`, `material`, `standard`, `size`, `name`, `surface`, and `barcode`.
