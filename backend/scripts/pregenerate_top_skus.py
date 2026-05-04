import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.database import init_db
from app.services.jobs import QUEUE_BATCH_PREGENERATE, enqueue_generation_job

DEFAULT_INPUT = ROOT.parent / "data" / "top_skus.example.json"


def verify_redis_connection() -> None:
    try:
        import redis as redis_lib

        client = redis_lib.Redis.from_url(settings.redis_url or "redis://localhost:6379")
        client.ping()
        print(f"Redis connected: {settings.redis_url or 'redis://localhost:6379'}")
    except Exception as exc:
        print(f"Redis not reachable: {exc}")
        print("Fix REDIS_URL or run without --verify-redis for local development.")
        raise SystemExit(1) from exc


def queue_jobs(*, rows: list[dict], queue_name: str, fmt: str, quality: str) -> list[dict]:
    jobs: list[dict] = []
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        job = enqueue_generation_job(
            queue_name=queue_name,
            product_id=row["product_id"],
            params=row["params"],
            fmt=fmt,
            quality=quality,
        )
        jobs.append(job.__dict__)
        print(f"[{index}/{total}] queued {job.job_id} status={job.status}")
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Queue pregeneration jobs for top SKU definitions.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--queue", default=QUEUE_BATCH_PREGENERATE)
    parser.add_argument("--format", default="glb", choices=["glb", "step", "stl"])
    parser.add_argument("--quality", default="preview", choices=["preview", "engineering"])
    parser.add_argument("--verify-redis", action="store_true")
    args = parser.parse_args()

    if args.verify_redis:
        verify_redis_connection()

    init_db()
    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    jobs = queue_jobs(rows=rows, queue_name=args.queue, fmt=args.format, quality=args.quality)
    print(json.dumps(jobs, indent=2, sort_keys=True))
    print("")
    print(f"Queued {len(jobs)} jobs on queue '{args.queue}'")


if __name__ == "__main__":
    main()
