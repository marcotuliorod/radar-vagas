import json
from pathlib import Path

import responses

from radar.connectors.ashby import AshbyConnector
from radar.connectors.greenhouse import GreenhouseConnector
from radar.connectors.gupy import GupyConnector
from radar.connectors.lever import LeverConnector
from radar.models import Company

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict | list:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@responses.activate
def test_greenhouse_connector_normalizes_jobs(make_company):
    company = make_company(
        ats_provider=Company.AtsProvider.GREENHOUSE,
        ats_board_url="https://boards.greenhouse.io/exemploco",
    )
    responses.add(
        responses.GET,
        "https://boards-api.greenhouse.io/v1/boards/exemploco/jobs",
        json=_load_fixture("greenhouse_sample.json"),
        status=200,
    )

    jobs = GreenhouseConnector().fetch_jobs(company)

    assert len(jobs) == 2
    first = jobs[0]
    assert first.external_id == "4020123"
    assert first.title == "Product Manager Senior"
    assert first.location == "São Paulo, SP"
    assert first.source == "greenhouse"
    assert first.published_at_estimated is False
    # Segunda vaga não tem first_published -> cai para updated_at como estimativa
    assert jobs[1].published_at_estimated is True


@responses.activate
def test_lever_connector_normalizes_jobs(make_company):
    company = make_company(
        ats_provider=Company.AtsProvider.LEVER,
        ats_board_url="https://jobs.lever.co/exemploco",
    )
    responses.add(
        responses.GET,
        "https://api.lever.co/v0/postings/exemploco",
        json=_load_fixture("lever_sample.json"),
        status=200,
    )

    jobs = LeverConnector().fetch_jobs(company)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.external_id == "abc-123"
    assert job.title == "Product Owner Pleno"
    assert job.work_model == "remote"
    assert job.source == "lever"
    assert job.published_at is not None


@responses.activate
def test_ashby_connector_normalizes_jobs(make_company):
    company = make_company(
        ats_provider=Company.AtsProvider.ASHBY,
        ats_board_url="https://jobs.ashbyhq.com/exemploco",
    )
    responses.add(
        responses.GET,
        "https://api.ashbyhq.com/posting-api/job-board/exemploco",
        json=_load_fixture("ashby_sample.json"),
        status=200,
    )

    jobs = AshbyConnector().fetch_jobs(company)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.external_id == "xyz-789"
    assert job.title == "Head of Product"
    assert job.work_model == ""  # isRemote: false
    assert job.source == "ashby"


@responses.activate
def test_gupy_connector_normalizes_jobs(make_company):
    company = make_company(
        ats_provider=Company.AtsProvider.GUPY,
        ats_board_url="https://exemploco.gupy.io/api/job_postings",
    )
    responses.add(
        responses.GET,
        "https://exemploco.gupy.io/api/job_postings",
        json=_load_fixture("gupy_sample.json"),
        status=200,
    )

    jobs = GupyConnector().fetch_jobs(company)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.external_id == "998877"
    assert job.title == "Product Owner Sênior"
    assert "Belo Horizonte" in job.location
    assert job.source == "gupy"


@responses.activate
def test_connector_retries_on_server_error_then_succeeds(make_company, monkeypatch):
    monkeypatch.setattr("radar.connectors.base.time.sleep", lambda *_: None)
    company = make_company(
        ats_provider=Company.AtsProvider.GREENHOUSE,
        ats_board_url="https://boards.greenhouse.io/exemploco",
    )
    responses.add(
        responses.GET,
        "https://boards-api.greenhouse.io/v1/boards/exemploco/jobs",
        status=503,
    )
    responses.add(
        responses.GET,
        "https://boards-api.greenhouse.io/v1/boards/exemploco/jobs",
        json=_load_fixture("greenhouse_sample.json"),
        status=200,
    )

    jobs = GreenhouseConnector().fetch_jobs(company)

    assert len(jobs) == 2
