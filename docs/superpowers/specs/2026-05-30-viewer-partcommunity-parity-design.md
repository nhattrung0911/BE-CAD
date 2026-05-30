# Viewer Render-Quality Parity with partcommunity (CADENAS 3Dfindit) — Design

**Date:** 2026-05-30
**Status:** Draft for review
**Author:** Codex (pair: dungnt)

## Goal

Make the Fastener CAD Workbench 3D preview look like the reference CADENAS
3Dfindit viewer (studied live at airtac-embedded.partcommunity.com):
**mượt (smooth) – nét (sharp) – chính xác (accurate)**.

This spec is **render quality only**. The 3D dimension annotations are
**removed entirely** (user-approved) — the part is shown clean, like the
reference 3D tab. Params stay editable in the existing side panel.

## Scope

**In scope (this spec):**
- Metal **matcap** material (procedurally generated steel matcap PNG).
- CAD **feature/silhouette edge lines** on the part.
- **Soft contact shadow** grounding the part.
- **Gradient background** behind a transparent canvas.
- **Crisp anti-aliasing** (MSAA via `antialias:true`, DPR up to 2).
- **ViewCube** gizmo (snap to Front/Right/Top/etc).
- **Smooth damped orbit; auto-rotate OFF by default** (reference is static).
- **Remove** the 3D dimension annotations from the viewer.
- Fix the existing **GLB material-mutation / GPU-buffer leak** while we are in
  this code (clone scene per URL + `useGLTF.clear(url)` on unmount).

**Explicitly OUT of scope (each a separate future spec — do NOT build here):**
- Viewer chrome: 3D/2D/Dimension tabs, toolbar, fullscreen, screenshot.
- Multi-format download buttons (GLB/STEP/STL) + job polling UI.
- 2D orthographic drawing (OCC HLR → SVG), dimensioned drawing.
- PDF datasheet (reportlab — confirmed installed 4.4.9, for later).
- Section-plane tool, measure tool.
- Auth UI, backend security fixes, catalog UX, production polish.

No backend changes. No new npm dependencies — every technique below ships in the
already-installed `@react-three/drei` + `three`. The only new asset is one
matcap PNG that we generate and commit.

## Reference Findings (measured live, not guessed)

From the running reference viewer (`browser_evaluate` on its canvas):

- WebGL2, context **`antialias: true`, `SAMPLES = 4`** → real MSAA 4×, DPR ≈ 1.
  (Earlier supersample guess was wrong — corrected here.)
- Canvas background **`rgba(0,0,0,0)` (transparent)** → the subtle near-white→grey
  **gradient lives on a parent element** behind the canvas.
- Part is **shaded grey metal** with **dark silhouette + feature edge lines**
  (technical-drawing look) and a **soft contact shadow** grounding it; crevices
  read darker (AO-like).
- **ViewCube** top-right; **static by default** (no auto-rotate), smooth damped
  manual orbit.

## Architecture

Extract the viewer we are rewriting into `frontend-demo/src/viewer/` so the
rebuilt viewer is not buried in the 1267-line `App.jsx`. **Scoped extraction
only** — move the viewer concerns we touch; do not refactor catalog / auth /
diagnostics code.

```
frontend-demo/src/viewer/
  Stage.jsx          # <Canvas>, lights, ContactShadows, ViewCube, OrbitControls
  FastenerModel.jsx  # GLB load, clone, matcap swap, <Edges>, bbox report, cleanup
  matcap.js          # tiny: resolves the matcap texture (cached singleton)
frontend-demo/public/
  matcap-steel.png   # generated, committed
frontend-demo/scripts/
  gen-matcap.mjs      # deterministic brushed-steel matcap generator (committed)
```

`App.jsx` keeps owning state/data flow; it renders `<Stage modelUrl=... />`
instead of the inline `ViewerStage`. The old `DimAnnotations`, `DimMeasure`,
`DimLeader`, `ArrowHead`, and the `annotations` prop wiring are deleted from the
viewer path. (Backend still returns annotations; the FE simply stops drawing
them — no contract break.)

## Render Recipe

| Quality target | Technique |
|---|---|
| Crisp AA ("nét") | `<Canvas dpr={[1,2]} gl={{ antialias: true, alpha: true }}>` |
| CAD edge lines ("nét") | drei `<Edges threshold={20} color="#363b42" />` on the part |
| Metal material ("mượt") | `THREE.MeshMatcapMaterial` + `matcap-steel.png` |
| Grounding shadow | drei `<ContactShadows opacity={0.35} blur={2.4} scale=fit />` |
| Background gradient | CSS `radial-gradient` on the wrapper div, transparent canvas |
| Orientation | drei `<GizmoHelper><GizmoViewcube/></GizmoHelper>` |
| Smooth control | `<OrbitControls enableDamping dampingFactor={0.1}>`, **autoRotate off** |
| Framing | drei `<Bounds fit clip observe>` (already used) |
| Dims | **removed** from viewer |

**Matcap generation** (`scripts/gen-matcap.mjs`, Node + `pngjs` or raw buffer,
run once, output committed): a 512×512 sphere-mapped brushed-steel matcap —
bright specular top-left, mid-grey body, darker rim — written deterministically
(no time-seeded RNG; brushed streaks from a fixed sine pattern). Committed to
`public/matcap-steel.png` so the build needs no generation step.

**Leak fix** (`FastenerModel.jsx`): `useGLTF(url)` returns a cached scene shared
across mounts. We `scene.clone(true)`, swap material on the **clone**, and on
unmount call `useGLTF.clear(url)` + dispose cloned geometries/materials. This
fixes the GPU-buffer growth when switching many variants (original audit item).

## Testing Strategy

- **Pure logic (vitest, no WebGL — TDD, test first):** the matcap pixel
  generator's color ramp is deterministic — unit-test that `gen-matcap` produces
  a fixed center/edge luminance (bright center, darker rim) and stable bytes for
  a fixed size. Any extracted helper (e.g. edge-threshold or fit math) gets a
  unit test. Existing `viewerControls.test.js` stays green (auto-rotate default
  flips to off — update that expectation).
- **3D render (Playwright, real app):** cadquery 2.7.0 installed,
  `MODEL_SYNC_GENERATION=true` → GLB generates inline. Same verify loop used for
  the button head: load app, screenshot the M3 button head, confirm — matcap
  metal material, visible edge lines, soft contact shadow, gradient background,
  ViewCube present, **no dimension clutter**, static (not spinning). Compare
  against `ref-airtac-1.png`.
- **Gates:** `cd frontend-demo; npm.cmd run build` (exit 0) and
  `npm.cmd run test` (vitest). Backend untouched, but run
  `python -m pytest -q -p no:cacheprovider` once to prove no regression.

## Risks & Mitigations

1. **Matcap look underwhelming** — iterate the generator's ramp; matcap is
   data-only so tuning is a re-run, no code-path risk. Fallback: a known free
   CC0 steel matcap (license-checked) if procedural can't match.
2. **`<Edges>` noisy on threaded shanks** (many facets) — tune `threshold`
   (angle in degrees) up until only true feature edges show; verify on the
   threaded bolt, not just the button head.
3. **App.jsx churn** — keep extraction strictly to the viewer; diff stays in
   `src/viewer/` + the one `App.jsx` swap point.
4. **GitNexus MCP unavailable this session** (AGENTS.md mandates impact
   analysis) — substitute manual call-site mapping + `git status`; note in PR.

## Success Criteria

1. Side-by-side, the preview reads as the same class of render as
   partcommunity: crisp edges, metal matcap, soft contact shadow, gradient bg,
   ViewCube, static smooth orbit, **no dim clutter**.
2. Switching through many variants does not grow GPU memory unbounded
   (leak fixed).
3. `npm run build` + vitest green; backend pytest still green; live Playwright
   render check passes against the reference.
