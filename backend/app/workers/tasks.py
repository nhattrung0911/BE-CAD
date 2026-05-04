try:
    from celery import Celery
except ImportError:
    Celery = None

from app.core.config import settings
from app.services.jobs import QUEUE_BATCH_PREGENERATE, QUEUE_CAD_GENERATE, QUEUE_ENGINEERING_STEP, QUEUE_PREVIEW_FAST
from app.services.job_runner import run_model_generation_job

if Celery:
    celery_app = Celery(
        "fastener_cad",
        broker=settings.redis_url or "memory://",
        backend=settings.redis_url or "cache+memory://",
    )
    celery_app.conf.task_routes = {
        "app.workers.tasks.generate_preview": {"queue": QUEUE_PREVIEW_FAST},
        "app.workers.tasks.generate_cad": {"queue": QUEUE_CAD_GENERATE},
        "app.workers.tasks.generate_engineering_step": {"queue": QUEUE_ENGINEERING_STEP},
        "app.workers.tasks.batch_pregenerate": {"queue": QUEUE_BATCH_PREGENERATE},
    }
else:
    celery_app = None


def _task(fn):
    return celery_app.task(fn) if celery_app else fn


@_task
def generate_preview(job_id: str) -> str:
    return run_generation_job(job_id)["status"]


@_task
def generate_cad(job_id: str) -> str:
    return run_generation_job(job_id)["status"]


@_task
def generate_engineering_step(job_id: str) -> str:
    return run_generation_job(job_id)["status"]


@_task
def batch_pregenerate(job_ids: list[str]) -> list[str]:
    return [run_generation_job(job_id)["status"] for job_id in job_ids]


def run_generation_job(job_id: str) -> dict:
    return run_model_generation_job(job_id)


def dispatch_generation_job(queue_name: str, job_id: str) -> None:
    if celery_app is None or not settings.redis_url:
        return
    task_by_queue = {
        QUEUE_PREVIEW_FAST: generate_preview,
        QUEUE_CAD_GENERATE: generate_cad,
        QUEUE_ENGINEERING_STEP: generate_engineering_step,
        QUEUE_BATCH_PREGENERATE: generate_cad,
    }
    task = task_by_queue[queue_name]
    task.apply_async(args=[job_id], queue=queue_name)
