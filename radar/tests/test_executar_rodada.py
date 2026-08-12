from radar import tasks
from radar.connectors.base import RawJob
from radar.models import Company, Job, RunLog


def _raw_job():
    return RawJob(
        external_id="ext-1",
        title="Product Owner Sênior",
        location="São Paulo",
        description_raw="Vaga de Product Owner Sênior.",
        url_apply="https://example.com/jobs/1",
        source="greenhouse",
    )


def test_executar_rodada_end_to_end_happy_path(make_company, monkeypatch):
    company = make_company(tier=Company.Tier.A)

    monkeypatch.setattr(
        tasks, "CONNECTORS_BY_PROVIDER", {"greenhouse": type("C", (), {"fetch_jobs": staticmethod(lambda c: [_raw_job()])})()}
    )
    monkeypatch.setattr(tasks, "reconstruct_brief", lambda job: {"perfil_alvo": "PO sênior"})
    monkeypatch.setattr(tasks, "detect_knockouts", lambda job, brief: {"knockouts": [], "veredito": "aprovado"})
    monkeypatch.setattr(tasks, "apply_knockout_result", lambda job, result: False)

    def fake_score_job(job, brief):
        job.score = 90
        job.recruiter_score = 88
        job.status = Job.Status.DOSSIER_PENDING
        return {}, 500

    monkeypatch.setattr(tasks, "score_job", fake_score_job)

    def fake_generate_boolean_string(job):
        job.boolean_string = "(PO) AND fintech"
        return {"boolean_string": job.boolean_string}, 100

    monkeypatch.setattr(tasks, "generate_boolean_string", fake_generate_boolean_string)

    result = tasks.executar_rodada(slot="R1", tiers=["A", "B", "C"])

    run_log = RunLog.objects.get(pk=result["run_log_id"])
    assert run_log.companies_polled == 1
    assert run_log.jobs_found == 1
    assert run_log.jobs_scored == 1
    assert run_log.status == RunLog.Status.COMPLETED

    job = Job.objects.get(company=company, external_id="ext-1")
    assert job.status == Job.Status.DOSSIER_PENDING
    assert job.score == 90
    assert job.recruiter_score == 88


def test_executar_rodada_isolates_connector_failure(make_company, monkeypatch):
    make_company(tier=Company.Tier.A, ats_provider=Company.AtsProvider.GREENHOUSE)

    def _boom(_company):
        raise ConnectionError("ATS fora do ar")

    monkeypatch.setattr(
        tasks, "CONNECTORS_BY_PROVIDER", {"greenhouse": type("C", (), {"fetch_jobs": staticmethod(_boom)})()}
    )

    result = tasks.executar_rodada(slot="R1", tiers=["A", "B", "C"])

    run_log = RunLog.objects.get(pk=result["run_log_id"])
    assert run_log.status == RunLog.Status.COMPLETED_WITH_ERRORS
    assert run_log.jobs_found == 0
    assert len(run_log.errors) == 1
    assert Job.objects.count() == 0
