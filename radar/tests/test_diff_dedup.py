from datetime import datetime, timezone as dt_timezone

from radar.connectors.base import RawJob
from radar.models import Job
from radar.services.dedup import compute_description_hash, find_duplicate, normalize_text
from radar.services.diff import diff_jobs


def _raw_job(external_id="ext-1", title="Product Owner", location="São Paulo", description="Descrição X"):
    return RawJob(
        external_id=external_id,
        title=title,
        location=location,
        description_raw=description,
        url_apply="https://example.com/jobs/1",
        source="greenhouse",
        published_at=datetime(2026, 8, 1, tzinfo=dt_timezone.utc),
    )


def test_diff_detects_new_job(make_company):
    company = make_company()
    result = diff_jobs(company, [_raw_job()])
    assert len(result.new_raw_jobs) == 1
    assert result.closed_jobs == []


def test_diff_ignores_already_known_job(make_company):
    company = make_company()
    Job.objects.create(
        company=company,
        external_id="ext-1",
        title="Product Owner",
        source=Job.Source.GREENHOUSE,
    )
    result = diff_jobs(company, [_raw_job()])
    assert result.new_raw_jobs == []


def test_diff_closes_job_missing_from_payload(make_company):
    company = make_company()
    job = Job.objects.create(
        company=company,
        external_id="ext-vanished",
        title="Vaga sumida",
        source=Job.Source.GREENHOUSE,
    )
    result = diff_jobs(company, [_raw_job(external_id="ext-1")])
    job.refresh_from_db()
    assert job.closed_at is not None
    assert job in result.closed_jobs


def test_normalize_text_strips_punctuation_and_case():
    assert normalize_text("Product Owner, Sênior!") == "product owner sênior"


def test_find_duplicate_by_title_and_location(make_company):
    company = make_company()
    Job.objects.create(
        company=company,
        external_id="ext-old",
        title="Product Owner Sênior",
        location="São Paulo",
        description_raw="Outra descrição",
        source=Job.Source.GREENHOUSE,
    )
    duplicate = find_duplicate(
        company, _raw_job(external_id="ext-new", title="product owner sênior", location="São Paulo")
    )
    assert duplicate is not None


def test_find_duplicate_by_description_hash(make_company):
    company = make_company()
    description = "Descrição idêntica em ambas as fontes."
    Job.objects.create(
        company=company,
        external_id="ext-old",
        title="Título A",
        location="Remoto",
        description_raw=description,
        description_hash=compute_description_hash(description),
        source=Job.Source.LEVER,
    )
    duplicate = find_duplicate(
        company,
        _raw_job(external_id="ext-new", title="Título completamente diferente", location="Híbrido", description=description),
    )
    assert duplicate is not None


def test_find_duplicate_returns_none_for_genuinely_new_job(make_company):
    company = make_company()
    Job.objects.create(
        company=company,
        external_id="ext-old",
        title="Analista de Dados",
        location="Remoto",
        description_raw="Descrição totalmente diferente sobre análise de dados.",
        source=Job.Source.GREENHOUSE,
    )
    duplicate = find_duplicate(company, _raw_job(title="Engenheiro de Software", location="Curitiba"))
    assert duplicate is None
