from app.cad.template_base import CadTemplate
from app.cad.templates.hex_bolt import HexBoltTemplate
from app.cad.templates.washer import WasherTemplate
from app.cad.templates.retaining_ring import RetainingRingTemplate


class TemplateRegistry:
    def __init__(self) -> None:
        self.templates: list[CadTemplate] = [
            HexBoltTemplate(),
            WasherTemplate(),
            RetainingRingTemplate(),
        ]

    def get_by_product(self, product_id: str) -> CadTemplate:
        if "hex-bolt" in product_id:
            return self.get_by_family("hex_bolt")
        if "washer" in product_id:
            return self.get_by_family("washer")
        if "retaining" in product_id or "gb891" in product_id:
            return self.get_by_family("retaining_ring")
        raise KeyError(f"No template registered for product_id={product_id}")

    def get_by_family(self, family: str) -> CadTemplate:
        for template in self.templates:
            if template.family == family:
                return template
        raise KeyError(f"No template registered for family={family}")


template_registry = TemplateRegistry()
