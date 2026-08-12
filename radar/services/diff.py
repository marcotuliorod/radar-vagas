"""Diff de coleta — RF-03.3: vaga nova por comparação de `external_id`;
vaga que sumiu do payload do ATS é considerada fechada."""

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from radar.connectors.base import RawJob
from radar.models import Company, Job


@dataclass
class DiffResult:
    new_raw_jobs: list[RawJob]
    closed_jobs: list[Job]


def diff_jobs(company: Company, raw_jobs: list[RawJob]) -> DiffResult:
    open_jobs_by_external_id = {
        job.external_id: job
        for job in Job.objects.filter(company=company, closed_at__isnull=True)
    }
    incoming_ids = {rj.external_id for rj in raw_jobs}

    new_raw_jobs = [rj for rj in raw_jobs if rj.external_id not in open_jobs_by_external_id]
    closed_jobs = [
        job for external_id, job in open_jobs_by_external_id.items()
        if external_id not in incoming_ids
    ]

    if closed_jobs:
        now = timezone.now()
        for job in closed_jobs:
            job.closed_at = now
        Job.objects.bulk_update(closed_jobs, ["closed_at"])

    return DiffResult(new_raw_jobs=new_raw_jobs, closed_jobs=closed_jobs)
