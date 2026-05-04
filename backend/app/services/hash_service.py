import hashlib
import json
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_params_hash(product_id: str, template_version: str, quality: str, fmt: str, params: dict[str, Any]) -> str:
    payload = {
        "product_id": product_id,
        "template_version": template_version,
        "quality": quality,
        "format": fmt,
        "params": params,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
