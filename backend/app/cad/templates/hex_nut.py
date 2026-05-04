import json

from app.cad.template_base import CadTemplate, GeneratedModel


class HexNutTemplate(CadTemplate):
    family = "hex_nut"
    supported_standards = ["ISO4032", "DIN934", "GB6170"]
    required_params = ["d", "s", "m"]

    def generate(self, params: dict, fmt: str, quality: str) -> GeneratedModel:
        self.validate_params(params)
        payload = {
            "generator": "mock",
            "template": "hex_nut",
            "format": fmt,
            "quality": quality,
            "params": params,
            "geometry_plan": {
                "hex_body": f"polygon(6, s={params['s']}) x h={params['m']}mm",
                "bore": f"circle(d/2={float(params['d']) / 2})",
                "chamfer": "both faces",
            },
        }
        return GeneratedModel(
            content=json.dumps(payload, sort_keys=True, indent=2).encode("utf-8"),
            format=fmt,
            metadata=payload,
        )
