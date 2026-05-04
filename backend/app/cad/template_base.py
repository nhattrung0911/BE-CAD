from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class GeneratedModel:
    content: bytes
    format: str
    metadata: dict[str, Any]


class CadTemplate(ABC):
    family: str
    supported_standards: list[str]
    required_params: list[str]

    def validate_params(self, params: dict[str, Any]) -> None:
        missing = [p for p in self.required_params if p not in params]
        if missing:
            raise ValueError(f"Missing required params: {missing}")

    @abstractmethod
    def generate(self, params: dict[str, Any], fmt: str, quality: str) -> GeneratedModel:
        raise NotImplementedError
