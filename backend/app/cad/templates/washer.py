import json
from app.cad.template_base import CadTemplate, GeneratedModel


class WasherTemplate(CadTemplate):
    family = "washer"
    supported_standards = ["ISO7089", "DIN125"]
    required_params = ["OD", "ID", "h"]

    def generate(self, params: dict, fmt: str, quality: str) -> GeneratedModel:
        self.validate_params(params)
        payload = {
            "generator": "mock",
            "template": "washer",
            "format": fmt,
            "quality": quality,
            "params": params,
            "geometry_plan": "ring extrude from OD/ID with thickness h",
        }
        return GeneratedModel(
            content=json.dumps(payload, sort_keys=True, indent=2).encode("utf-8"),
            format=fmt,
            metadata=payload,
        )
