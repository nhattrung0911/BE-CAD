# Resource Sizing

## Worker sizing formula

```text
required_worker_processes =
ceil(peak_requests_per_second * uncached_ratio * avg_generation_seconds / target_utilization)
```

Example:

```text
20 rps * 0.02 uncached * 4 seconds / 0.70 = 2.28 => 3 workers
```

## Queue separation

- `preview_fast`: vendor 3D -> GLB, small parametric preview.
- `cad_generate`: uncached preview generation.
- `engineering_step`: high quality STEP/STL, lower priority.
- `batch_pregenerate`: nightly catalog jobs.

## Cache strategy

Cache key:

```text
model:{product_id}:{template_version}:{quality}:{format}:{sha256(params_json)}
```

Artifact path:

```text
artifacts/{product_id}/{template_version}/{param_hash}/{quality}.{format}
```

## Targets

- Metadata API p95: < 150 ms.
- Cached model resolve p95: < 200 ms.
- Preview GLB target: 200 KB - 1 MB.
- Cache hit rate after pregeneration: > 95% for popular SKUs.
