# Backend CAD-Delivery Quality — Design

**Date:** 2026-05-31
**Status:** Approved (scope + sequence confirmed by user)
**Author:** Codex (pair: dungnt)

## Context & Correction

An earlier spec this session aimed at *frontend* viewer render parity. The user
corrected the mission: **this project is the BACKEND for CAD delivery**, not a
full web frontend. AGENTS.md agrees — `frontend-demo/` is "a thin API contract
demo, not the production frontend." All frontend polish work has been reverted.

The reference (CADENAS 3Dfindit) is, at its core, a **backend that generates and
serves accurate CAD** (3D model, 2D drawing, datasheet) from parameters. We match
that backend capability. "mượt – nét – chính xác" = **smooth, sharp, accurate
generated CAD output**, server-side.

## Goal

Make the generated CAD output production-grade and complete:
clean accurate solids for every family, smooth tessellation, valid STEP/STL/GLB,
plus backend-generated 2D drawings and PDF datasheets.

## Scope & Sequence (user-approved: all three, sequenced)

**Phase 1 — Geometry quality + mesh tessellation.**
- LOD-driven GLB tessellation (low/medium/high → real triangle-density tiers,
  size-relative). Today all three LODs emit an identical mesh at fixed
  `tolerance=0.1, angularTolerance=0.2`; curves on small parts (M3 dome) are
  visibly faceted. Make `high` smooth, `low` light, with a file-size ceiling.
- Verify STEP/STL exports are valid solids (non-empty, correct bbox); GLB bbox
  matches the parametric inputs for every family.
- Geometry accuracy pass per family (threads, chamfers, bores, domes) against the
  parametric inputs — extend the existing fake-cadquery + real-cadquery tests.
- Clean the duplicate `queue_for_request` definition in `services/jobs.py`.

**Phase 2 — 2D orthographic drawing (OCC HLR → SVG).**
- `projection_service.py`: OpenCASCADE hidden-line removal
  (`OCP.HLRBRep.HLRBRep_Algo`, confirmed available) → visible/hidden edges for
  front/top/right, serialized to SVG.
- `GET /api/v1/drawings/{variant_id}/2d.svg`, content-addressed + cached like
  GLBs, public rate-limited.
- Fallback permitted if HLR proves too costly: orthographic edge projection in
  numpy from the tessellated mesh. Decide after a spike.

**Phase 3 — PDF datasheet.**
- `datasheet_service.py` (reportlab 4.4.9, confirmed installed): A4 PDF with
  title block (product/standard/SKU), an embedded view (the 2D SVG rasterized or
  a rendered PNG), and the full parameter table (code/label/value/unit).
- `GET /api/v1/drawings/{variant_id}/datasheet.pdf`, public rate-limited.

Each phase: its own TDD cycle (test first), the AGENTS.md gate
`python -m pytest -q -p no:cacheprovider`, and a real-cadquery verification.

## Architecture (respects AGENTS.md layer boundaries)

```
backend/app/cad/backends.py          # Phase 1: LOD tessellation in _export_glb
backend/app/cad/tessellation.py      # Phase 1: pure tolerance-tier helper (unit-testable)
backend/app/services/jobs.py         # Phase 1: remove duplicate queue_for_request
backend/app/services/projection_service.py  # Phase 2: OCC HLR -> SVG
backend/app/api/routes_drawings.py          # Phase 2+3: /2d.svg, /datasheet.pdf
backend/app/services/datasheet_service.py   # Phase 3: reportlab PDF
backend/tests/test_tessellation.py          # Phase 1
backend/tests/test_projection_service.py    # Phase 2
backend/tests/test_datasheet_service.py     # Phase 3
backend/tests/test_drawings_routes.py       # Phase 2+3 route contract
```

No API contract breaks. New routes only. `requirements.txt` gains `reportlab`
(already importable in this env; pin for reproducibility).

## Phase 1 Detail — Tessellation Tiers

Pure helper `tessellation_for_lod(lod, part_size_mm) -> (linear_tol, angular_tol)`,
unit-tested without OCC. Tolerances are size-relative so a 6 mm screw and a 100 mm
ring both tessellate proportionally:

| LOD | linear tol | angular tol (rad) |
|---|---|---|
| low | max(size·0.02, 0.15) | 0.50 (~29°) |
| medium | max(size·0.010, 0.05) | 0.30 (~17°) |
| high | max(size·0.004, 0.02) | 0.15 (~8.6°) |

`_export_glb` reads `params["lod"]` (already threaded into params via
`params_for_lod`) and the model bbox, then passes the tier to
`assembly.export(tolerance=..., angularTolerance=...)`. A hard triangle/byte
ceiling guards against pathological density; if exceeded, step back one tier and
log it (no silent truncation).

**Tests (TDD):**
- Pure: tiers monotonic (low ≥ medium ≥ high tolerances), floors respected,
  angular strictly decreasing low→high. Deterministic.
- Real cadquery (`importorskip`): same part at low/medium/high →
  `tris(low) < tris(medium) < tris(high)`, all bboxes equal within tolerance,
  high under the byte ceiling.
- STEP/STL: exported bytes non-empty, STEP starts `ISO-10303`, STL parses, bbox
  matches inputs.

## Testing Strategy

- Backend gate: `cd backend; python -m pytest -q -p no:cacheprovider` after each
  phase. Real-cadquery tests run (cadquery 2.7.0 present), not skipped.
- Phase 2/3 artifacts verified by content assertions (SVG has non-empty edge
  paths and correct viewBox; PDF starts `%PDF` and contains the param values).
- Live spot check via the existing inline-generation path
  (`MODEL_SYNC_GENERATION=true`).

## Risks

1. **OCC HLR wiring (Phase 2)** — highest. Spike first; numpy edge-projection
   fallback permitted without re-approval.
2. **Tessellation file-size blowup at high LOD** — byte ceiling + tier step-back.
3. **GitNexus MCP unavailable** (AGENTS.md mandates impact analysis) — substitute
   manual call-site mapping + `git status` + `pytest`; note in PR.

## Success Criteria

1. low/medium/high produce measurably different, correct meshes; high is smooth
   (angular ≤ ~9°), files within the ceiling.
2. STEP/STL/GLB all valid for every family, bbox matches parametric inputs.
3. `/drawings/{variant}/2d.svg` returns a correct orthographic drawing.
4. `/drawings/{variant}/datasheet.pdf` returns a datasheet with the right params.
5. `pytest` green after every phase; no API contract break.
