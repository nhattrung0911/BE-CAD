from fastapi import APIRouter, HTTPException

from app.schemas.model_job import ModelJobResponse
from app.services.job_runner import get_model_job_payload

router = APIRouter(prefix="/model-jobs", tags=["model-jobs"])


@router.get("/{job_id}", response_model=ModelJobResponse)
def get_model_job(job_id: str):
    payload = get_model_job_payload(job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Model job not found")
    return payload
