# Backend Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the backend fail fast on unsafe production settings and reject false async-queue success paths so runtime behavior stays deterministic and debuggable.

**Architecture:** Keep the current FastAPI/service/repository split, but harden the system at the production contract edges first. Startup config must reject unsafe production mode, queue-dependent paths must fail synchronously when dispatch infrastructure is unavailable, and Redis-backed cache behavior must stop silently degrading in strict mode.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic Settings, Celery, Redis, pytest

---

## File Structure

- Modify: `backend/app/core/config.py`
  - Tighten production configuration validation.
- Modify: `backend/app/services/cache_service.py`
  - Make Redis fallback explicit and strict when production-ready Redis is required.
- Modify: `backend/app/workers/tasks.py`
  - Add explicit async-dispatch availability checks and remove false-success dispatch behavior.
- Modify: `backend/app/services/model_resolver.py`
  - Refuse queueing paths when async dispatch is unavailable.
- Modify: `backend/app/api/routes_models.py`
  - Translate queue infrastructure failures into a clear API-level `503`.
- Modify: `backend/app/api/routes_geometry.py`
  - Translate queue infrastructure failures into a clear API-level `503`.
- Modify: `backend/tests/test_foundation_hardening.py`
  - Add regression coverage for production guards and queue/cache hardening.
- Modify: `.gitignore`
  - Ignore Alembic `__pycache__` artifacts created during test runs.

### Task 1: Production Config Fail-Fast

**Files:**
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_foundation_hardening.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_production_settings_require_admin_api_key():
    with pytest.raises(ValueError) as exc:
        Settings(
            environment="production",
            cad_backend="cadquery",
            model_sync_generation=False,
            auto_create_schema=False,
            require_redis_for_ready=True,
            admin_api_key=None,
        )
    assert "ADMIN_API_KEY" in str(exc.value)


def test_production_settings_require_async_generation():
    with pytest.raises(ValueError) as exc:
        Settings(
            environment="production",
            cad_backend="cadquery",
            model_sync_generation=True,
            auto_create_schema=False,
            require_redis_for_ready=True,
            admin_api_key="x" * 32,
        )
    assert "MODEL_SYNC_GENERATION=false" in str(exc.value)
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run: `python -m pytest -q -p no:cacheprovider backend/tests/test_foundation_hardening.py -k "admin_api_key or async_generation"`
Expected: FAIL because current production validation does not enforce these rules.

- [ ] **Step 3: Implement the minimal production guard changes**

```python
@model_validator(mode="after")
def validate_production_settings(self) -> "Settings":
    if self.environment != "production":
        return self
    if self.cad_backend == "mock":
        raise ValueError("CAD_BACKEND=mock is not allowed in production. Set CAD_BACKEND=cadquery")
    if self.model_sync_generation:
        raise ValueError("MODEL_SYNC_GENERATION=false is required in production.")
    if self.auto_create_schema:
        raise ValueError("AUTO_CREATE_SCHEMA=true is not allowed in production. Use Alembic migrations.")
    if not self.require_redis_for_ready:
        raise ValueError("REQUIRE_REDIS_FOR_READY must be true in production to prevent split-brain cache.")
    if not self.admin_api_key:
        raise ValueError("ADMIN_API_KEY must be set in production.")
    return self
```

- [ ] **Step 4: Run the targeted tests to verify GREEN**

Run: `python -m pytest -q -p no:cacheprovider backend/tests/test_foundation_hardening.py -k "admin_api_key or async_generation"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/tests/test_foundation_hardening.py
git commit -m "fix: harden production config contract"
```

### Task 2: Strict Async Dispatch Contract

**Files:**
- Modify: `backend/app/workers/tasks.py`
- Modify: `backend/app/services/model_resolver.py`
- Modify: `backend/app/api/routes_models.py`
- Modify: `backend/app/api/routes_geometry.py`
- Test: `backend/tests/test_foundation_hardening.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_dispatch_generation_job_raises_without_redis():
    original_redis_url = settings.redis_url
    settings.redis_url = None
    try:
        with pytest.raises(RuntimeError, match="REDIS_URL is required"):
            dispatch_generation_job("preview_fast", "test-job-123")
    finally:
        settings.redis_url = original_redis_url


def test_models_resolve_returns_503_when_async_dispatch_is_unavailable():
    original_sync = settings.model_sync_generation
    original_redis = settings.redis_url
    settings.model_sync_generation = False
    settings.redis_url = None
    try:
        response = client.post(
            "/api/v1/models/resolve",
            json={
                "product_id": "hex-bolt-iso4014",
                "params": {"d": 8, "L": 30, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
                "format": "glb",
                "quality": "preview",
            },
        )
        assert response.status_code == 503
    finally:
        settings.model_sync_generation = original_sync
        settings.redis_url = original_redis
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run: `python -m pytest -q -p no:cacheprovider backend/tests/test_foundation_hardening.py -k "dispatch_generation_job or returns_503"`
Expected: FAIL because current code only warns and still returns queued behavior.

- [ ] **Step 3: Implement explicit async-dispatch availability checks**

```python
class AsyncDispatchUnavailable(RuntimeError):
    pass


def ensure_async_dispatch_available() -> None:
    if not settings.redis_url:
        raise AsyncDispatchUnavailable(
            "REDIS_URL is required for async generation. Set REDIS_URL or use MODEL_SYNC_GENERATION=true for local dev."
        )
    if Celery is None:
        raise AsyncDispatchUnavailable("celery package is required for async generation")


def dispatch_generation_job(queue_name: str, job_id: str) -> None:
    ensure_async_dispatch_available()
    app = get_celery_app()
    task = task_by_queue[queue_name]
    task.apply_async(args=[job_id], queue=queue_name)
```

```python
if lock is None:
    ensure_async_dispatch_available()
    job = enqueue_generation_job(...)
    return ModelResolveResponse(...)

if not self._may_generate_inline(request):
    ensure_async_dispatch_available()
    job = enqueue_generation_job(...)
    dispatch_generation_job(job.queue_name, job.job_id)
    return ModelResolveResponse(...)
```

```python
except AsyncDispatchUnavailable as exc:
    raise HTTPException(status_code=503, detail=str(exc))
```

- [ ] **Step 4: Run the targeted tests to verify GREEN**

Run: `python -m pytest -q -p no:cacheprovider backend/tests/test_foundation_hardening.py -k "dispatch_generation_job or returns_503"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/workers/tasks.py backend/app/services/model_resolver.py backend/app/api/routes_models.py backend/app/api/routes_geometry.py backend/tests/test_foundation_hardening.py
git commit -m "fix: fail fast when async generation infrastructure is unavailable"
```

### Task 3: Strict Redis Cache Semantics

**Files:**
- Modify: `backend/app/services/cache_service.py`
- Test: `backend/tests/test_foundation_hardening.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_redis_cache_raises_when_strict_mode_and_connection_fails(monkeypatch):
    settings.require_redis_for_ready = True

    class FakeRedisClient:
        def ping(self):
            raise RuntimeError("boom")

    class FakeRedisModule:
        class Redis:
            @staticmethod
            def from_url(*args, **kwargs):
                return FakeRedisClient()

    monkeypatch.setitem(sys.modules, "redis", FakeRedisModule())

    with pytest.raises(RuntimeError, match="Cannot fall back to in-memory cache"):
        RedisCache("redis://example", InMemoryCache())
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run: `python -m pytest -q -p no:cacheprovider backend/tests/test_foundation_hardening.py -k "strict_mode_and_connection_fails"`
Expected: FAIL because current RedisCache swallows connection errors.

- [ ] **Step 3: Implement strict Redis fallback behavior**

```python
class RedisCache:
    def __init__(self, url: str, fallback: InMemoryCache) -> None:
        self.fallback = fallback
        self._strict = settings.require_redis_for_ready
        self.client = None
        try:
            import redis
            client = redis.Redis.from_url(url, decode_responses=False, socket_connect_timeout=3, socket_timeout=3)
            client.ping()
            self.client = client
        except Exception as exc:
            if self._strict:
                raise RuntimeError(
                    "Redis connection failed and REQUIRE_REDIS_FOR_READY=true. "
                    "Cannot fall back to in-memory cache in production."
                ) from exc
```

- [ ] **Step 4: Run the targeted tests to verify GREEN**

Run: `python -m pytest -q -p no:cacheprovider backend/tests/test_foundation_hardening.py -k "strict_mode_and_connection_fails"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cache_service.py backend/tests/test_foundation_hardening.py
git commit -m "fix: enforce strict redis cache behavior"
```

### Task 4: Repo Hygiene For Repeatable Verification

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add Alembic bytecode cache ignores**

```gitignore
backend/alembic/__pycache__/
backend/alembic/versions/__pycache__/
```

- [ ] **Step 2: Verify status stays clean after test runs**

Run: `git status --short`
Expected: no new Alembic `__pycache__` entries after verification commands.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore alembic bytecode artifacts"
```

## Self-Review

- Spec coverage:
  - Production fail-fast: covered by Task 1.
  - Async queue truthfulness: covered by Task 2.
  - Redis/cache strictness: covered by Task 3.
  - Verification hygiene: covered by Task 4.
- Placeholder scan:
  - No TODO/TBD placeholders left in executable steps.
- Type consistency:
  - `AsyncDispatchUnavailable` is introduced once in worker/task flow and consumed consistently in both route layers and resolver flow.
