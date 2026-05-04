import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import init_db
from app.services.jobs import QUEUE_BATCH_PREGENERATE, enqueue_generation_job


def main() -> None:
    parser = argparse.ArgumentParser(description="Queue pregeneration jobs for top SKU definitions.")
    parser.add_argument("--input", default="../data/top_skus.example.json")
    parser.add_argument("--format", default="glb", choices=["glb", "step", "stl"])
    parser.add_argument("--quality", default="preview", choices=["preview", "engineering"])
    args = parser.parse_args()

    init_db()
    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    jobs = []
    for row in rows:
        jobs.append(
            enqueue_generation_job(
                queue_name=QUEUE_BATCH_PREGENERATE,
                product_id=row["product_id"],
                params=row["params"],
                fmt=args.format,
                quality=args.quality,
            )
        )
    print(json.dumps([job.__dict__ for job in jobs], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
