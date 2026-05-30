import functools

from app.domain.geometry_hashes import build_geometry_hashes
from app.schemas.product import ParameterSpec, Product, ProductVariant


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
    "hex-nut-iso4032": Product(
        product_id="hex-nut-iso4032",
        standard="ISO4032",
        family="hex_nut",
        name="Hex nut ISO 4032",
        parameters=[
            ParameterSpec(name="d", label="Nominal diameter", values=[6, 8, 10, 12, 14, 16, 20, 24]),
            ParameterSpec(name="s", label="Across flats"),
            ParameterSpec(name="m", label="Nut height"),
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
    "hex-bolt-din933": Product(
        product_id="hex-bolt-din933",
        standard="DIN933",
        family="hex_bolt",
        name="Hex bolt DIN 933 (fully threaded)",
        parameters=[
            ParameterSpec(name="d", label="Nominal diameter"),
            ParameterSpec(name="L", label="Total length"),
            ParameterSpec(name="P", label="Thread pitch"),
            ParameterSpec(name="k", label="Head height"),
            ParameterSpec(name="s", label="Across flats"),
            ParameterSpec(name="b", label="Thread length (= L for fully threaded)"),
        ],
    ),
    "hex-nut-din6330": Product(
        product_id="hex-nut-din6330",
        standard="DIN6330",
        family="hex_nut",
        name="High hex nut DIN 6330 (1.5d)",
        parameters=[
            ParameterSpec(name="d", label="Nominal diameter"),
            ParameterSpec(name="s", label="Across flats"),
            ParameterSpec(name="m", label="Nut height (high)"),
        ],
    ),
    "button-head-iso7380": Product(
        product_id="button-head-iso7380",
        standard="ISO7380",
        family="button_head",
        name="Button head socket cap ISO 7380",
        parameters=[
            ParameterSpec(name="d", label="Nominal diameter"),
            ParameterSpec(name="L", label="Total length"),
            ParameterSpec(name="P", label="Thread pitch"),
            ParameterSpec(name="dk", label="Head outer diameter"),
            ParameterSpec(name="k", label="Head height"),
            ParameterSpec(name="s", label="Hex socket size"),
            ParameterSpec(name="t", label="Hex socket depth"),
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
            "params": {"d": 10, "L": 40, "P": 1.5, "k": 6.4, "s": 16, "b": 26},
            "material": "steel",
        },
        {
            "variant_id": "hex-bolt-iso4014-m12x50",
            "sku": "HEX-BOLT-ISO4014-M12X50",
            "label": "M12 x 50 mm",
            "diameter_label": "M12",
            "params": {"d": 12, "L": 50, "P": 1.75, "k": 7.5, "s": 18, "b": 30},
            "material": "steel",
        },
    ],
    "hex-nut-iso4032": [
        {
            "variant_id": "hex-nut-iso4032-m6",
            "sku": "HEX-NUT-ISO4032-M6",
            "label": "M6",
            "diameter_label": "M6",
            "params": {"d": 6, "s": 10.0, "m": 5.2},
            "material": "carbon_steel",
        },
        {
            "variant_id": "hex-nut-iso4032-m8",
            "sku": "HEX-NUT-ISO4032-M8",
            "label": "M8",
            "diameter_label": "M8",
            "params": {"d": 8, "s": 13.0, "m": 6.8},
            "material": "carbon_steel",
        },
        {
            "variant_id": "hex-nut-iso4032-m10",
            "sku": "HEX-NUT-ISO4032-M10",
            "label": "M10",
            "diameter_label": "M10",
            "params": {"d": 10, "s": 16.0, "m": 8.4},
            "material": "carbon_steel",
        },
        {
            "variant_id": "hex-nut-iso4032-m12",
            "sku": "HEX-NUT-ISO4032-M12",
            "label": "M12",
            "diameter_label": "M12",
            "params": {"d": 12, "s": 18.0, "m": 10.8},
            "material": "carbon_steel",
        },
        {
            "variant_id": "hex-nut-iso4032-m14",
            "sku": "HEX-NUT-ISO4032-M14",
            "label": "M14",
            "diameter_label": "M14",
            "params": {"d": 14, "s": 21.0, "m": 12.8},
            "material": "carbon_steel",
        },
        {
            "variant_id": "hex-nut-iso4032-m16",
            "sku": "HEX-NUT-ISO4032-M16",
            "label": "M16",
            "diameter_label": "M16",
            "params": {"d": 16, "s": 24.0, "m": 14.8},
            "material": "carbon_steel",
        },
        {
            "variant_id": "hex-nut-iso4032-m20",
            "sku": "HEX-NUT-ISO4032-M20",
            "label": "M20",
            "diameter_label": "M20",
            "params": {"d": 20, "s": 30.0, "m": 18.0},
            "material": "carbon_steel",
        },
        {
            "variant_id": "hex-nut-iso4032-m24",
            "sku": "HEX-NUT-ISO4032-M24",
            "label": "M24",
            "diameter_label": "M24",
            "params": {"d": 24, "s": 36.0, "m": 21.5},
            "material": "carbon_steel",
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
            "params": {"d": 10, "L": 45, "P": 1.5, "k": 6.4, "s": 16, "b": 26},
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
    "hex-bolt-din933": [
        {
            "variant_id": "hex-bolt-din933-m1_6x2",
            "sku": "HEX-BOLT-DIN933-M1.6X2",
            "label": "M1.6 x 2 mm",
            "diameter_label": "M1.6",
            "params": {"d": 1.6, "L": 2.0, "P": 0.35, "k": 1.1, "s": 3.2, "b": 2.0},
            "material": "steel",
        },
        {
            "variant_id": "hex-bolt-din933-m6x16",
            "sku": "HEX-BOLT-DIN933-M6X16",
            "label": "M6 x 16 mm",
            "diameter_label": "M6",
            "params": {"d": 6, "L": 16, "P": 1.0, "k": 4.0, "s": 10, "b": 16},
            "material": "steel",
        },
        {
            "variant_id": "hex-bolt-din933-m8x20",
            "sku": "HEX-BOLT-DIN933-M8X20",
            "label": "M8 x 20 mm",
            "diameter_label": "M8",
            "params": {"d": 8, "L": 20, "P": 1.25, "k": 5.3, "s": 13, "b": 20},
            "material": "steel",
        },
    ],
    "hex-nut-din6330": [
        {
            "variant_id": "hex-nut-din6330-m8",
            "sku": "HEX-NUT-DIN6330-M8",
            "label": "M8 high nut",
            "diameter_label": "M8",
            "params": {"d": 8, "s": 13.0, "m": 12.0},
            "material": "carbon_steel",
        },
        {
            "variant_id": "hex-nut-din6330-m10",
            "sku": "HEX-NUT-DIN6330-M10",
            "label": "M10 high nut",
            "diameter_label": "M10",
            "params": {"d": 10, "s": 16.0, "m": 15.0},
            "material": "carbon_steel",
        },
        {
            "variant_id": "hex-nut-din6330-m12",
            "sku": "HEX-NUT-DIN6330-M12",
            "label": "M12 high nut",
            "diameter_label": "M12",
            "params": {"d": 12, "s": 18.0, "m": 18.0},
            "material": "carbon_steel",
        },
    ],
    "button-head-iso7380": [
        {
            "variant_id": "button-head-iso7380-m3x6",
            "sku": "BUTTON-HEAD-ISO7380-M3X6",
            "label": "M3 x 6 mm",
            "diameter_label": "M3",
            "params": {"d": 3, "L": 6, "P": 0.5, "dk": 5.7, "k": 1.65, "s": 2.0, "t": 1.04},
            "material": "alloy_steel",
        },
        {
            "variant_id": "button-head-iso7380-m5x10",
            "sku": "BUTTON-HEAD-ISO7380-M5X10",
            "label": "M5 x 10 mm",
            "diameter_label": "M5",
            "params": {"d": 5, "L": 10, "P": 0.8, "dk": 9.5, "k": 2.75, "s": 3.0, "t": 1.56},
            "material": "alloy_steel",
        },
        {
            "variant_id": "button-head-iso7380-m8x16",
            "sku": "BUTTON-HEAD-ISO7380-M8X16",
            "label": "M8 x 16 mm",
            "diameter_label": "M8",
            "params": {"d": 8, "L": 16, "P": 1.25, "dk": 14.0, "k": 4.4, "s": 5.0, "t": 2.6},
            "material": "alloy_steel",
        },
    ],
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
