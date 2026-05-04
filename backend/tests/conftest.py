import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./storage/test.db")

import pytest


@pytest.fixture(autouse=True)
def _reset_cad_backend_cache():
    """The cad backend is process-cached for perf; tests that monkeypatch
    sys.modules['cadquery'] need a fresh instance per case."""
    from app.cad.backends import reset_cad_backend_cache

    reset_cad_backend_cache()
    yield
    reset_cad_backend_cache()
