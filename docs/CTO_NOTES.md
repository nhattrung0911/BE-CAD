# CTO Notes for Dev Team

## Priority

Backend correctness and cache design are more important than FE polish.

## Key product principle

User browsing must be fast. CAD is background work. Most popular models must be pregenerated.

## Vendor 3D principle

If exact vendor 3D exists, use it. If not exact, never scale it for engineering use. Parametric template wins.

## Template principle

One family template can serve many standards if dimension mapping is explicit. Add standards by data first, code second.

## Legal note

Before production, confirm rights to store, transform, and redistribute vendor 2D/3D files.
