from typing import Literal

from pydantic import BaseModel


AssetFormat = Literal["glb", "step", "stl"]
LicenseStatus = Literal["pending", "approved", "restricted", "rejected"]
ValidationStatus = Literal["pending", "valid", "invalid"]


class VendorAssetResponse(BaseModel):
    id: int
    product_id: str
    format: AssetFormat
    filename: str
    storage_key: str
    url: str
    sha256: str
    file_size: int
    license_status: LicenseStatus
    validation_status: ValidationStatus
