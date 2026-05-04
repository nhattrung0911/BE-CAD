METRIC_HELP = {
    "cad_platform_requests_total": "Total HTTP requests",
    "cad_platform_request_latency_ms_total": "Total latency in milliseconds",
    "cad_platform_jobs_queued_total": "Total jobs queued",
    "cad_platform_jobs_completed_total": "Total jobs completed",
    "cad_platform_jobs_failed_total": "Total jobs failed",
    "cad_platform_cache_hits_total": "Cache hits",
    "cad_platform_cache_misses_total": "Cache misses",
    "cad_platform_generate_inline_total": "Total inline generations",
    "cad_platform_generate_inline_ms_total": "Total inline generation time in milliseconds",
}


def _new_metrics_store() -> dict[str, int]:
    return {name: 0 for name in METRIC_HELP}


_metrics_store = _new_metrics_store()


def reset_metrics() -> dict[str, int]:
    global _metrics_store
    _metrics_store = _new_metrics_store()
    return _metrics_store


def get_metrics_store() -> dict[str, int]:
    return _metrics_store


def record_request(*, elapsed_ms: int, metrics: dict[str, int]) -> None:
    metrics["cad_platform_requests_total"] += 1
    metrics["cad_platform_request_latency_ms_total"] += elapsed_ms


def record_cache_result(*, cache_status: str, metrics: dict[str, int]) -> None:
    key = "cad_platform_cache_hits_total" if cache_status == "hit" else "cad_platform_cache_misses_total"
    metrics[key] += 1


def record_job_queued(metrics: dict[str, int] | None = None) -> None:
    (metrics or _metrics_store)["cad_platform_jobs_queued_total"] += 1


def record_job_completed(metrics: dict[str, int] | None = None) -> None:
    (metrics or _metrics_store)["cad_platform_jobs_completed_total"] += 1


def record_job_failed(metrics: dict[str, int] | None = None) -> None:
    (metrics or _metrics_store)["cad_platform_jobs_failed_total"] += 1


def record_inline_generation(*, elapsed_ms: int, metrics: dict[str, int] | None = None) -> None:
    target = metrics or _metrics_store
    target["cad_platform_generate_inline_total"] += 1
    target["cad_platform_generate_inline_ms_total"] += elapsed_ms


def render_prometheus(metrics: dict[str, int]) -> str:
    lines: list[str] = []
    for metric_name, help_text in METRIC_HELP.items():
        lines.extend(
            [
                f"# HELP {metric_name} {help_text}",
                f"# TYPE {metric_name} counter",
                f"{metric_name} {metrics[metric_name]}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
