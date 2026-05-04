# Architecture Blueprint

## High-level flow

```text
External sources
(GlobalFastener / GPYH / internal upload)
        |
        v
Ingestion Service
- SVG/PDF/DXF/STEP/STL/GLB import
- checksum, raw storage
- metadata extraction
        |
        v
Normalization
- standard code: ISO/DIN/GB/JIS
- unit normalization to mm
- parameter mapping: d, D, L, P, h, s, b, OD, ID
        |
        v
Model Resolver
1. cached exact artifact
2. exact vendor 3D model
3. parametric template generation
4. 2D metadata fallback
        |
        v
CAD Workers
- preview GLB queue
- engineering STEP queue
- batch pregeneration queue
        |
        v
Artifact Storage + CDN
- preview.glb
- engineering.step
- optional.stl
- thumbnail.webp
        |
        v
Backend API
- product metadata
- parameter schema
- model artifact URL
- job status
```

## Core services

- API Service: FastAPI, no heavy CAD work in request.
- Model Resolver: chooses cached/vendor/generated path.
- CAD Worker: CPU-bound generation and conversion.
- Artifact Service: local dev storage now; S3/MinIO in production.
- Cache Service: in-memory now; Redis in production.
- Ingestion Service: parse vendor SVG/table labels and ingest raw CAD assets.

## Why hybrid

Vendor 3D is fast when exact. Parametric templates are flexible when vendor assets are absent or not editable. 2D drawings are valuable for metadata and validation, but not sufficient as the only source for general 3D reconstruction.
