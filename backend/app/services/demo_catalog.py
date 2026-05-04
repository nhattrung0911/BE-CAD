import functools

from app.core.config import settings
from app.schemas.product import ParameterSpec, Product, ProductVariant
from app.services.hash_service import stable_params_hash


CATALOG = {
    "hex-bolt-iso4014": Product(
        product_id="hex-bolt-iso4014",
        standard="ISO4014",
        family="hex_bolt",
        name="Hex bolt ISO 4014",
        parameters=[
            ParameterSpec(name="d", label="Nominal diameter", values=[6, 8, 10, 12]),
            ParameterSpec(name="L", label="Total length", values=[20, 25, 30, 40, 50]),
            ParameterSpec(name="P", label="Thread pitch"),
            ParameterSpec(name="k", label="Head height"),
            ParameterSpec(name="s", label="Across flats"),
            ParameterSpec(name="b", label="Thread length"),
        ],
    ),
    "retaining-ring-gb891": Product(
        product_id="retaining-ring-gb891",
        standard="GB891",
        family="retaining_ring",
        name="Screw-fastened retaining ring GB891",
        parameters=[
            ParameterSpec(name="OD", label="Outer diameter"),
            ParameterSpec(name="d1", label="Hole diameter"),
            ParameterSpec(name="h", label="Thickness"),
        ],
    ),
    "washer-iso7089": Product(
        product_id="washer-iso7089",
        standard="ISO7089",
        family="washer",
        name="Plain washer ISO 7089",
        parameters=[
            ParameterSpec(name="OD", label="Outer diameter"),
            ParameterSpec(name="ID", label="Inner diameter"),
            ParameterSpec(name="h", label="Thickness"),
        ],
    ),
    "hex-bolt-din931": Product(
        product_id="hex-bolt-din931",
        standard="DIN931",
        family="hex_bolt",
        name="Hex bolt DIN 931",
        parameters=[
            ParameterSpec(name="d", label="Nominal diameter", values=[8, 10]),
            ParameterSpec(name="L", label="Total length", values=[35, 45]),
            ParameterSpec(name="P", label="Thread pitch"),
            ParameterSpec(name="k", label="Head height"),
            ParameterSpec(name="s", label="Across flats"),
            ParameterSpec(name="b", label="Thread length"),
        ],
    ),
    "washer-din125": Product(
        product_id="washer-din125",
        standard="DIN125",
        family="washer",
        name="Plain washer DIN 125",
        parameters=[
            ParameterSpec(name="OD", label="Outer diameter"),
            ParameterSpec(name="ID", label="Inner diameter"),
            ParameterSpec(name="h", label="Thickness"),
        ],
    ),
}


VARIANTS = {
    "hex-bolt-iso4014": [
        {
            "variant_id": "hex-bolt-iso4014-m8x30",
            "sku": "HEX-BOLT-ISO4014-M8X30",
            "label": "M8 x 30 mm",
            "diameter_label": "M8",
            "params": {"d": 8, "L": 30, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
            "material": "steel",
        },
        {
            "variant_id": "hex-bolt-iso4014-m8x40",
            "sku": "HEX-BOLT-ISO4014-M8X40",
            "label": "M8 x 40 mm",
            "diameter_label": "M8",
            "params": {"d": 8, "L": 40, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
            "material": "steel",
        },
        {
            "variant_id": "hex-bolt-iso4014-m10x40",
            "sku": "HEX-BOLT-ISO4014-M10X40",
            "label": "M10 x 40 mm",
            "diameter_label": "M10",
            "params": {"d": 10, "L": 40, "P": 1.5, "k": 6.4, "s": 17, "b": 26},
            "material": "steel",
        },
        {
            "variant_id": "hex-bolt-iso4014-m12x50",
            "sku": "HEX-BOLT-ISO4014-M12X50",
            "label": "M12 x 50 mm",
            "diameter_label": "M12",
            "params": {"d": 12, "L": 50, "P": 1.75, "k": 7.5, "s": 19, "b": 30},
            "material": "steel",
        },
    ],
    "washer-iso7089": [
        {
            "variant_id": "washer-iso7089-m8",
            "sku": "WASHER-ISO7089-M8",
            "label": "M8 washer",
            "diameter_label": "M8",
            "params": {"OD": 16, "ID": 8.4, "h": 1.6},
            "material": "steel",
        },
        {
            "variant_id": "washer-iso7089-m10",
            "sku": "WASHER-ISO7089-M10",
            "label": "M10 washer",
            "diameter_label": "M10",
            "params": {"OD": 20, "ID": 10.5, "h": 2.0},
            "material": "steel",
        },
    ],
    "retaining-ring-gb891": [
        {
            "variant_id": "retaining-ring-gb891-100",
            "sku": "RETAINING-GB891-100",
            "label": "GB891 retaining ring 100",
            "diameter_label": "100",
            "params": {"OD": 100, "d1": 74, "h": 3.0},
            "material": "65Mn",
        },
    ],
    "hex-bolt-din931": [
        {
            "variant_id": "hex-bolt-din931-m8x35",
            "sku": "HEX-BOLT-DIN931-M8X35",
            "label": "M8 x 35 mm",
            "diameter_label": "M8",
            "params": {"d": 8, "L": 35, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
            "material": "steel",
        },
        {
            "variant_id": "hex-bolt-din931-m10x45",
            "sku": "HEX-BOLT-DIN931-M10X45",
            "label": "M10 x 45 mm",
            "diameter_label": "M10",
            "params": {"d": 10, "L": 45, "P": 1.5, "k": 6.4, "s": 17, "b": 26},
            "material": "steel",
        },
    ],
    "washer-din125": [
        {
            "variant_id": "washer-din125-m8",
            "sku": "WASHER-DIN125-M8",
            "label": "M8 washer",
            "diameter_label": "M8",
            "params": {"OD": 16, "ID": 8.4, "h": 1.6},
            "material": "steel",
        },
    ],
}


def params_for_lod(params: dict, lod: str) -> dict:
    return {**params, "lod": lod}


def build_geometry_hashes(product_id: str, params: dict) -> dict[str, str]:
    return {
        f"{lod}_hash": stable_params_hash(
            product_id,
            settings.template_version,
            "preview",
            "glb",
            params_for_lod(params, lod),
        )
        for lod in ["low", "medium", "high"]
    }


class DemoCatalogSource:
    def list_products(self) -> list[Product]:
        return list(CATALOG.values())

    def get_product(self, product_id: str) -> Product:
        return CATALOG[product_id]

    def list_variants(self, product_id: str) -> list[ProductVariant]:
        product = self.get_product(product_id)
        variants = []
        for raw in VARIANTS.get(product_id, []):
            variants.append(
                ProductVariant(
                    product_id=product_id,
                    standard=product.standard,
                    geometry=build_geometry_hashes(product_id, raw["params"]),
                    **raw,
                )
            )
        return variants

    @functools.cached_property
    def _variant_lookup(self) -> dict[str, ProductVariant]:
        lookup = {}
        for product_id in VARIANTS:
            for variant in self.list_variants(product_id):
                lookup[variant.variant_id] = variant
        return lookup

    def get_variant(self, variant_id: str) -> ProductVariant:
        variant = self._variant_lookup.get(variant_id)
        if variant is None:
            raise KeyError(variant_id)
        return variant

    def has_products(self) -> bool:
        return bool(CATALOG)
