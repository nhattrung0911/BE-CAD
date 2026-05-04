from fastapi.testclient import TestClient

from app.bootstrap import database as database_bootstrap
from app.bootstrap.seed_catalog import seed_demo_catalog
from app.core.config import settings
from app.core.database import Base, engine
from app.main import app
from app.schemas.product import ParameterSpec, Product, ProductVariant
from app.services.product_service import ProductService


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    settings.environment = "local"
    settings.require_redis_for_ready = False


def test_product_service_can_use_injected_catalog_source():
    custom_product = Product(
        product_id="custom-bolt",
        standard="CSTM-1",
        family="hex_bolt",
        name="Custom bolt",
        parameters=[ParameterSpec(name="d", label="Diameter")],
    )
    custom_variant = ProductVariant(
        variant_id="custom-bolt-m8",
        product_id="custom-bolt",
        sku="CUSTOM-BOLT-M8",
        label="Custom bolt M8",
        diameter_label="M8",
        params={"d": 8},
        material="steel",
        standard="CSTM-1",
        geometry={"low_hash": "a", "medium_hash": "b", "high_hash": "c"},
    )

    class StubCatalogSource:
        def list_products(self):
            return [custom_product]

        def get_product(self, product_id: str):
            if product_id != "custom-bolt":
                raise KeyError(product_id)
            return custom_product

        def list_variants(self, product_id: str):
            if product_id != "custom-bolt":
                raise KeyError(product_id)
            return [custom_variant]

        def get_variant(self, variant_id: str):
            if variant_id != "custom-bolt-m8":
                raise KeyError(variant_id)
            return custom_variant

        def has_products(self) -> bool:
            return True

    service = ProductService(catalog_source=StubCatalogSource(), allow_demo_fallback=False)

    assert [product.product_id for product in service.list_products()] == ["custom-bolt"]
    assert service.get_product("custom-bolt").standard == "CSTM-1"
    assert service.get_variant("custom-bolt-m8").sku == "CUSTOM-BOLT-M8"


def test_ready_reports_catalog_empty_in_production():
    original_environment = settings.environment
    settings.environment = "production"
    try:
        response = client.get("/ready")

        assert response.status_code == 503
        assert response.json()["checks"]["catalog"] == "empty"
    finally:
        settings.environment = original_environment


def test_seed_demo_catalog_makes_production_ready():
    original_environment = settings.environment
    settings.environment = "production"
    try:
        seeded = seed_demo_catalog()
        response = client.get("/ready")

        assert seeded == 5
        assert response.status_code == 200
        assert response.json()["checks"]["catalog"] == "ok"
    finally:
        settings.environment = original_environment


def test_database_bootstrap_stamps_complete_legacy_schema(monkeypatch):
    class FakeInspector:
        def get_table_names(self):
            return list(database_bootstrap.LEGACY_BASELINE_TABLES)

    calls = []

    monkeypatch.setattr(database_bootstrap, "inspect", lambda _: FakeInspector())
    monkeypatch.setattr(
        database_bootstrap.command,
        "stamp",
        lambda config, revision: calls.append(("stamp", revision)),
    )
    monkeypatch.setattr(
        database_bootstrap.command,
        "upgrade",
        lambda config, revision: calls.append(("upgrade", revision)),
    )

    result = database_bootstrap.ensure_database_schema_current()

    assert result == "stamped_legacy_and_upgraded"
    assert calls == [
        ("stamp", database_bootstrap.BASELINE_REVISION),
        ("upgrade", "head"),
    ]


def test_database_bootstrap_rejects_partial_legacy_schema(monkeypatch):
    class FakeInspector:
        def get_table_names(self):
            return ["artifacts"]

    monkeypatch.setattr(database_bootstrap, "inspect", lambda _: FakeInspector())

    try:
        database_bootstrap.ensure_database_schema_current()
    except RuntimeError as exc:
        assert "partial legacy schema" in str(exc)
    else:
        raise AssertionError("Expected partial legacy schema to be rejected")
