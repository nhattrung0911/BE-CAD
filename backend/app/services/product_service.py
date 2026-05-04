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
        return self.catalog_source.has_products()

    def has_catalog_data(self) -> bool:
        if self.has_persistent_catalog_data():
            return True
        if self._allow_demo_fallback():
            return self.demo_catalog_source.has_products()
        return False

    def _selected_source(self):
        if self.catalog_source.has_products():
            return self.catalog_source
        if self._allow_demo_fallback():
            return self.demo_catalog_source
        return self.catalog_source

    def _allow_demo_fallback(self) -> bool:
        if self.allow_demo_fallback is not None:
            return self.allow_demo_fallback
        return settings.environment != "production"


product_service = ProductService()
