from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import CatalogParameterSpec, CatalogProduct, CatalogVariant
from app.schemas.product import ParameterSpec, Product, ProductVariant
from app.services.demo_catalog import build_geometry_hashes


class CatalogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def has_products(self) -> bool:
        return self.session.scalar(select(CatalogProduct.id).limit(1)) is not None

    def list_products(self) -> list[Product]:
        products = self.session.scalars(select(CatalogProduct).order_by(CatalogProduct.product_id)).all()
        return [self._to_product(product) for product in products]

    def get_product(self, product_id: str) -> Product:
        product = self.session.scalar(select(CatalogProduct).where(CatalogProduct.product_id == product_id))
        if product is None:
            raise KeyError(product_id)
        return self._to_product(product)

    def list_variants(self, product_id: str) -> list[ProductVariant]:
        product = self.get_product(product_id)
        variants = self.session.scalars(
            select(CatalogVariant)
            .where(CatalogVariant.product_id == product_id)
            .order_by(CatalogVariant.variant_id)
        ).all()
        return [self._to_variant(product, variant) for variant in variants]

    def get_variant(self, variant_id: str) -> ProductVariant:
        variant = self.session.scalar(select(CatalogVariant).where(CatalogVariant.variant_id == variant_id))
        if variant is None:
            raise KeyError(variant_id)
        product = self.get_product(variant.product_id)
        return self._to_variant(product, variant)

    def replace_product_catalog(
        self,
        *,
        product: Product,
        variants: list[dict],
    ) -> None:
        product_id = product.product_id
        self.session.execute(delete(CatalogVariant).where(CatalogVariant.product_id == product_id))
        self.session.execute(delete(CatalogParameterSpec).where(CatalogParameterSpec.product_id == product_id))
        self.session.execute(delete(CatalogProduct).where(CatalogProduct.product_id == product_id))

        self.session.add(
            CatalogProduct(
                product_id=product.product_id,
                standard=product.standard,
                family=product.family,
                name=product.name,
                unit=product.unit,
            )
        )

        for sort_order, spec in enumerate(product.parameters):
            self.session.add(
                CatalogParameterSpec(
                    product_id=product_id,
                    name=spec.name,
                    label=spec.label,
                    type=spec.type,
                    unit=spec.unit,
                    required=spec.required,
                    values_json=spec.values,
                    sort_order=sort_order,
                )
            )

        for raw_variant in variants:
            self.session.add(
                CatalogVariant(
                    variant_id=raw_variant["variant_id"],
                    product_id=product_id,
                    sku=raw_variant["sku"],
                    label=raw_variant["label"],
                    diameter_label=raw_variant["diameter_label"],
                    params_json=raw_variant["params"],
                    material=raw_variant.get("material", "steel"),
                )
            )

        self.session.flush()

    def _to_product(self, product: CatalogProduct) -> Product:
        specs = self.session.scalars(
            select(CatalogParameterSpec)
            .where(CatalogParameterSpec.product_id == product.product_id)
            .order_by(CatalogParameterSpec.sort_order, CatalogParameterSpec.id)
        ).all()
        return Product(
            product_id=product.product_id,
            standard=product.standard,
            family=product.family,
            name=product.name,
            unit=product.unit,
            parameters=[
                ParameterSpec(
                    name=spec.name,
                    label=spec.label,
                    type=spec.type,
                    unit=spec.unit,
                    required=spec.required,
                    values=spec.values_json,
                )
                for spec in specs
            ],
        )

    def _to_variant(self, product: Product, variant: CatalogVariant) -> ProductVariant:
        return ProductVariant(
            variant_id=variant.variant_id,
            product_id=variant.product_id,
            sku=variant.sku,
            label=variant.label,
            diameter_label=variant.diameter_label,
            params=variant.params_json,
            material=variant.material,
            standard=product.standard,
            geometry=build_geometry_hashes(variant.product_id, variant.params_json),
        )
