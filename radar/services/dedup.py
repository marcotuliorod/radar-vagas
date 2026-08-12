"""Deduplicação — RF-03.5: chave `(company, título normalizado, localidade)`
+ similaridade de `description_hash`. Também expõe `compute_description_hash`,
usado pela camada de inteligência para o cache por vaga (RF-04.4)."""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher

from radar.connectors.base import RawJob
from radar.models import Company, Job

SIMILARITY_THRESHOLD = 0.92


def normalize_text(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^\w\s]", "", value)
    return re.sub(r"\s+", " ", value)


def compute_description_hash(description: str) -> str:
    normalized = normalize_text(description)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _descriptions_similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio() >= SIMILARITY_THRESHOLD


def find_duplicate(company: Company, raw_job: RawJob) -> Job | None:
    """Retorna o `Job` já existente que representa a mesma vaga, se houver."""

    normalized_title = normalize_text(raw_job.title)
    normalized_location = normalize_text(raw_job.location)
    description_hash = compute_description_hash(raw_job.description_raw)

    candidates = Job.objects.filter(company=company, closed_at__isnull=True)

    for job in candidates:
        same_key = (
            normalize_text(job.title) == normalized_title
            and normalize_text(job.location) == normalized_location
        )
        if same_key:
            return job
        if job.description_hash and job.description_hash == description_hash:
            return job
        if _descriptions_similar(job.description_raw, raw_job.description_raw):
            return job

    return None
