from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories.catalog import CatalogRepository
from app.schemas.product import ProductVariant
from app.services.demo_catalog import DemoCatalogSource


class DatabaseCatalogSource:
    def has_products(self) -> bool:
        with SessionLocal() as session:
            return CatalogRepository(session).has_products()

    def list_products(self):
        with SessionLocal() as session:
            return CatalogRepository(session).list_products()

    def get_product(self, product_id: str):
        with SessionLocal() as session:
            return CatalogRepository(session).get_product(product_id)

    def list_variants(self, product_id: str):
        with SessionLocal() as session:
            return CatalogRepository(session).list_variants(product_id)

    def get_variant(self, variant_id: str):
        with SessionLocal() as session:
            return CatalogRepository(session).get_variant(variant_id)


class CatalogStatusSnapshot(dict):
    @property
    def has_persistent_catalog(self) -> bool:
        return bool(self["persistent_catalog"])

    @property
    def demo_fallback_allowed(self) -> bool:
        return bool(self["demo_fallback_allowed"])

    @property
    def demo_catalog_available(self) -> bool:
        return bool(self["demo_catalog_available"])

    @property
    def selected_source(self) -> str:
        return str(self["selected_source"])


class ProductService:
    def __init__(
        self,
        *,
        catalog_source=None,
        demo_catalog_source=None,
        allow_demo_fallback: bool | None = None,
    ) -> None:
        self.catalog_source = catalog_source or DatabaseCatalogSource()
        self.demo_catalog_source = demo_catalog_source or DemoCatalogSource()
        self.allow_demo_fallback = allow_demo_fallback

    def list_products(self):
        return self._selected_source().list_products()

    def get_product(self, product_id: str):
        return self._selected_source().get_product(product_id)

    def validate_params(self, product_id: str, params: dict) -> None:
        product = self.get_product(product_id)
        missing = [
            spec.name
            for spec in product.parameters
            if spec.required and spec.name not in params
        ]
        if missing:
            raise ValueError({"error": "Invalid product parameters", "missing": missing})

    def list_variants(self, product_id: str) -> list[ProductVariant]:
        return self._selected_source().list_variants(product_id)

    def get_variant(self, variant_id: str) -> ProductVariant:
        return self._selected_source().get_variant(variant_id)

    def grouped_variants(self, product_id: str) -> dict:
        variants = self.list_variants(product_id)
        grouped: dict[str, list[dict]] = {}
        for variant in variants:
            grouped.setdefault(variant.diameter_label, []).append(variant.model_dump())
        return {
            "product_id": product_id,
            "total": len(variants),
            "grouped_by_diameter": grouped,
        }

    def has_persistent_catalog_data(self) -> bool:
        return self.catalog_status().has_persistent_catalog

    def has_catalog_data(self) -> bool:
        snapshot = self.catalog_status()
        return snapshot.has_persistent_catalog or (
            snapshot.demo_fallback_allowed and snapshot.demo_catalog_available
        )

    def catalog_status(self) -> CatalogStatusSnapshot:
        persistent_catalog = self.catalog_source.has_products()
        demo_fallback_allowed = self._allow_demo_fallback()
        demo_catalog_available = self.demo_catalog_source.has_products() if demo_fallback_allowed else False
        selected_source = "persistent" if persistent_catalog else "demo" if demo_catalog_available else "persistent"
        return CatalogStatusSnapshot(
            persistent_catalog=persistent_catalog,
            demo_fallback_allowed=demo_fallback_allowed,
            demo_catalog_available=demo_catalog_available,
            selected_source=selected_source,
        )

    def _selected_source(self):
        snapshot = self.catalog_status()
        if snapshot.has_persistent_catalog:
            return self.catalog_source
        if snapshot.demo_fallback_allowed and snapshot.demo_catalog_available:
            return self.demo_catalog_source
        return self.catalog_source

    def _allow_demo_fallback(self) -> bool:
        if self.allow_demo_fallback is not None:
            return self.allow_demo_fallback
        return settings.environment != "production"


product_service = ProductService()
