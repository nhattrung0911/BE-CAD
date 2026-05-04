import json

from app.cad.template_base import CadTemplate, GeneratedModel


class ButtonHeadTemplate(CadTemplate):
    family = "button_head"
    supported_standards = ["ISO7380"]
    required_params = ["d", "L", "P", "dk", "k", "s", "t"]

    def generate(self, params: dict, fmt: str, quality: str) -> GeneratedModel:
        self.validate_params(params)
        payload = {
            "generator": "mock",
            "template": "button_head",
            "format": fmt,
            "quality": quality,
            "params": params,
            "geometry_plan": {
                "head": "domed cylinder with hex socket",
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
