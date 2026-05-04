import json
from app.cad.template_base import CadTemplate, GeneratedModel


class RetainingRingTemplate(CadTemplate):
    family = "retaining_ring"
    supported_standards = ["GB891", "DIN471", "DIN472"]
    required_params = ["OD", "d1", "h"]

    def generate(self, params: dict, fmt: str, quality: str) -> GeneratedModel:
        self.validate_params(params)
        payload = {
            "generator": "mock",
            "template": "retaining_ring",
            "format": fmt,
            "quality": quality,
            "params": params,
            "geometry_plan": "ring body with gap and screw/end features",
        }
        return GeneratedModel(
            content=json.dumps(payload, sort_keys=True, indent=2).encode("utf-8"),
            format=fmt,
            metadata=payload,
        )
