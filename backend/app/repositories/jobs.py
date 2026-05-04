from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GenerationJob


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        job_id: str,
        queue_name: str,
        product_id: str,
        params: dict,
        params_hash: str,
        fmt: str,
        quality: str,
        status: str = "pending",
    ) -> GenerationJob:
        job = GenerationJob(
            job_id=job_id,
            queue_name=queue_name,
            product_id=product_id,
            params_json=params,
            params_hash=params_hash,
            format=fmt,
            quality=quality,
            status=status,
        )
        self.session.add(job)
        self.session.flush()
        return job

    def find_by_job_id(self, job_id: str) -> GenerationJob | None:
        return self.session.scalar(select(GenerationJob).where(GenerationJob.job_id == job_id))

    def mark_running(self, job: GenerationJob) -> GenerationJob:
        job.status = "running"
        job.error_message = None
        self.session.flush()
        return job

    def mark_done(self, job: GenerationJob, artifact_id: int) -> GenerationJob:
        job.status = "done"
        job.result_artifact_id = artifact_id
        job.error_message = None
        self.session.flush()
        return job

    def mark_failed(self, job: GenerationJob, error_message: str) -> GenerationJob:
        job.status = "failed"
        job.error_message = error_message[:1024]
        self.session.flush()
        return job

    def mark_pending(self, job: GenerationJob) -> GenerationJob:
        job.status = "pending"
        job.error_message = None
        self.session.flush()
        return job
