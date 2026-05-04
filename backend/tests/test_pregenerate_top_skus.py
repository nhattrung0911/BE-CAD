import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import pregenerate_top_skus


def test_queue_jobs_uses_requested_queue_and_returns_payloads(monkeypatch, capsys):
    queued = []

    def fake_enqueue_generation_job(*, queue_name, product_id, params, fmt, quality, template_version="v0"):
        queued.append((queue_name, product_id, params, fmt, quality))
        return SimpleNamespace(
            job_id=f"job_{queue_name}_{product_id}",
            queue_name=queue_name,
            status="pending",
            product_id=product_id,
            format=fmt,
            quality=quality,
            artifact_id=None,
            error_message=None,
        )

    monkeypatch.setattr(pregenerate_top_skus, "enqueue_generation_job", fake_enqueue_generation_job)

    rows = [{"product_id": "hex-nut-iso4032", "params": {"d": 8, "s": 13.0, "m": 6.8, "lod": "medium"}}]
    jobs = pregenerate_top_skus.queue_jobs(rows=rows, queue_name="batch_pregenerate", fmt="glb", quality="preview")

    assert len(jobs) == 1
    assert jobs[0]["queue_name"] == "batch_pregenerate"
    assert queued[0][1] == "hex-nut-iso4032"
    assert "[1/1] queued" in capsys.readouterr().out


def test_verify_redis_connection_exits_when_ping_fails(monkeypatch, capsys):
    class FakeRedisClient:
        def ping(self):
            raise RuntimeError("boom")

    class FakeRedisModule:
        class Redis:
            @staticmethod
            def from_url(url):
                return FakeRedisClient()

    monkeypatch.setitem(__import__("sys").modules, "redis", FakeRedisModule)

    with pytest.raises(SystemExit):
        pregenerate_top_skus.verify_redis_connection()

    assert "Redis not reachable" in capsys.readouterr().out


def test_production_top_skus_file_contains_hex_nut_entries():
    payload = json.loads((Path(__file__).resolve().parents[2] / "data" / "top_skus.production.json").read_text(encoding="utf-8"))

    assert any(row["product_id"] == "hex-nut-iso4032" for row in payload)
    assert any(row["product_id"] == "hex-bolt-iso4014" for row in payload)
    assert any(row["product_id"] == "washer-iso7089" for row in payload)
