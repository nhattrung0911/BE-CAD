import json
from app.cad.template_base import CadTemplate, GeneratedModel


class HexBoltTemplate(CadTemplate):
    family = "hex_bolt"
    supported_standards = ["ISO4014", "DIN931", "GB5782"]
    required_params = ["d", "L", "P", "k", "s", "b"]

    def generate(self, params: dict, fmt: str, quality: str) -> GeneratedModel:
        self.validate_params(params)

        # Production TODO:
        # - Replace this mock with CadQuery/OCC solid generation.
        # - Preview: simplified visual thread.
        # - Engineering: exact STEP with optional real thread.
        payload = {
            "generator": "mock",
            "template": "hex_bolt",
            "format": fmt,
            "quality": quality,
            "params": params,
            "geometry_plan": {
                "head": "hex prism with chamfer",
                "shank": "cylinder",
                "thread": "visual" if quality == "preview" else "engineering",
                "length_mm": params["L"],
            },
        }
        return GeneratedModel(
            content=json.dumps(payload, sort_keys=True, indent=2).encode("utf-8"),
            format=fmt,
            metadata=payload,
        )
