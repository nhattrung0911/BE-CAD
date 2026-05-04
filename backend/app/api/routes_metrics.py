from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["observability"])


@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics(request: Request) -> str:
    metrics = request.app.state.metrics
    lines = [
        "# HELP cad_platform_requests_total Total HTTP requests",
        "# TYPE cad_platform_requests_total counter",
        f'cad_platform_requests_total {metrics["cad_platform_requests_total"]}',
        "",
        "# HELP cad_platform_request_latency_ms_total Total latency in milliseconds",
        "# TYPE cad_platform_request_latency_ms_total counter",
        f'cad_platform_request_latency_ms_total {metrics["cad_platform_request_latency_ms_total"]}',
        "",
        "# HELP cad_platform_jobs_queued_total Total jobs queued",
        "# TYPE cad_platform_jobs_queued_total counter",
        f'cad_platform_jobs_queued_total {metrics["cad_platform_jobs_queued_total"]}',
        "",
        "# HELP cad_platform_cache_hits_total Cache hits",
        "# TYPE cad_platform_cache_hits_total counter",
        f'cad_platform_cache_hits_total {metrics["cad_platform_cache_hits_total"]}',
        "",
        "# HELP cad_platform_cache_misses_total Cache misses",
        "# TYPE cad_platform_cache_misses_total counter",
        f'cad_platform_cache_misses_total {metrics["cad_platform_cache_misses_total"]}',
    ]
    return "\n".join(lines) + "\n"
