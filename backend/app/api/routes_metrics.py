from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from app.services.observability import render_prometheus

router = APIRouter(tags=["observability"])


@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics(request: Request) -> str:
    return render_prometheus(request.app.state.metrics)
