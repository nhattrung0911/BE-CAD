from app.core.config import settings
from app.services.hash_service import stable_params_hash


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
