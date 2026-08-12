"""
Orquestração de uma rodada — §10.1 do PRD, sem as etapas de Fase 3 (gerar
CV/carta, parsing de ATS simulado, triagem em dois passes, gate). O poll dos
ATS roda em paralelo via `ThreadPoolExecutor` (é I/O-bound e não precisa de
uma fila Celery própria por empresa para nosso volume-alvo, ~150 empresas —
RNF-01: rodada completa em ≤25 min); o restante do pipeline roda
sequencialmente dentro da própria task, com retry local (RF-13.4) e captura
de erro por vaga (RF-13.5) para que uma falha isolada não derrube a rodada.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from radar.connectors import CONNECTORS_BY_PROVIDER
from radar.connectors.base import ConnectorError, RawJob
from radar.intelligence.boolean_string import generate_boolean_string
from radar.intelligence.brief import reconstruct_brief
from radar.intelligence.knockouts import apply_knockout_result, detect_knockouts
from radar.intelligence.scoring import score_job
from radar.models import Company, Job, RunLog
from radar.notifications.telegram import (
    notify_failure,
    notify_high_priority_job,
    notify_round_summary,
)
from radar.services import tier_promotion
from radar.services import sheets_sync
from radar.services.dedup import compute_description_hash, find_duplicate
from radar.services.diff import diff_jobs

logger = logging.getLogger(__name__)

HIGH_PRIORITY_TIER = "A"
HIGH_PRIORITY_RECRUITER_SCORE = 85
MAX_PROCESS_ATTEMPTS = 3


def determine_mode(slot: str) -> str:
    """RF-14.3/RF-14.4 — a grade (Anexo G / radarvagas/celery.py) só distingue
    R1 de R2-R4 por dia da semana; backlog (segunda) e reduzido (fim de
    semana) são detectados aqui, em runtime, e não por schedules separados."""

    if slot != "R1":
        return RunLog.Mode.NORMAL
    weekday = timezone.localtime(timezone.now()).weekday()  # 0 = segunda
    if weekday == 0:
        return RunLog.Mode.BACKLOG
    if weekday >= 5:
        return RunLog.Mode.REDUZIDO
    return RunLog.Mode.NORMAL


def _poll_company(company: Company) -> tuple[Company, list[RawJob] | None, Exception | None]:
    connector = CONNECTORS_BY_PROVIDER.get(company.ats_provider)
    if connector is None:
        return company, None, ConnectorError(f"Sem conector para provider '{company.ats_provider}'.")
    try:
        return company, connector.fetch_jobs(company), None
    except Exception as exc:  # noqa: BLE001 — RF-13.5: isolar falha de uma fonte
        return company, None, exc


def _poll_companies_parallel(
    companies: list[Company],
) -> list[tuple[Company, list[RawJob] | None, Exception | None]]:
    if not companies:
        return []
    with ThreadPoolExecutor(max_workers=min(10, len(companies))) as executor:
        futures = [executor.submit(_poll_company, c) for c in companies]
        return [future.result() for future in as_completed(futures)]


def _process_new_job(job: Job) -> int:
    """brief → knockouts → score duplo → (boolean string se dossier_pending).
    Levanta exceção se algo falhar; quem decide o retry é `_process_with_retry`."""

    tokens_used = 0
    brief = reconstruct_brief(job)

    knockout_result = detect_knockouts(job, brief)
    if apply_knockout_result(job, knockout_result):
        job.save()
        return tokens_used

    _, score_tokens = score_job(job, brief)
    tokens_used += score_tokens

    if job.status == Job.Status.DOSSIER_PENDING:
        _, boolean_tokens = generate_boolean_string(job)
        tokens_used += boolean_tokens

    job.save()
    return tokens_used


def _process_with_retry(job: Job, run_log: RunLog) -> int:
    """RF-13.4 — até 3 tentativas; falha isolada vai para `run_log.errors` e
    a vaga fica para a rodada seguinte assumir (RF-14.7 já cobre isso, pois o
    diff volta a enxergá-la como aberta e não processada)."""

    last_error: Exception | None = None
    for attempt in range(1, MAX_PROCESS_ATTEMPTS + 1):
        try:
            return _process_new_job(job)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "Falha ao processar job %s (tentativa %s/%s): %s",
                job.pk, attempt, MAX_PROCESS_ATTEMPTS, exc,
            )
    run_log.errors.append({"job_id": job.pk, "title": job.title, "error": str(last_error)})
    return 0


@shared_task(name="radar.tasks.executar_rodada")
def executar_rodada(slot: str, tiers: list[str]) -> dict:
    mode = determine_mode(slot)
    run_log = RunLog.objects.create(
        scheduled_slot=slot, mode=mode, started_at=timezone.now(), status=RunLog.Status.RUNNING
    )

    companies = list(Company.objects.filter(tier__in=tiers))
    poll_results = _poll_companies_parallel(companies)

    new_jobs: list[Job] = []
    for company, raw_jobs, error in poll_results:
        if error is not None:
            company.poll_error_count += 1
            company.save(update_fields=["poll_error_count"])
            run_log.errors.append({"company": company.name, "error": str(error)})
            if company.poll_error_count >= settings.RADAR_MAX_POLL_ERRORS:
                notify_failure(
                    f"{company.name} acumulou {company.poll_error_count} erros de poll "
                    "consecutivos — provável mudança de ATS (RF-02.5)."
                )
            continue

        company.poll_error_count = 0
        company.last_polled_at = timezone.now()
        company.save(update_fields=["poll_error_count", "last_polled_at"])

        diff_result = diff_jobs(company, raw_jobs)
        run_log.jobs_found += len(diff_result.new_raw_jobs)

        for raw_job in diff_result.new_raw_jobs:
            if find_duplicate(company, raw_job) is not None:
                continue
            job = Job.objects.create(
                company=company,
                external_id=raw_job.external_id,
                title=raw_job.title,
                location=raw_job.location,
                work_model=raw_job.work_model,
                description_raw=raw_job.description_raw,
                description_hash=compute_description_hash(raw_job.description_raw),
                url_apply=raw_job.url_apply,
                source=raw_job.source,
                published_at=raw_job.published_at,
                published_at_estimated=raw_job.published_at_estimated,
                found_in_run=run_log,
            )
            new_jobs.append(job)

    run_log.companies_polled = len(companies)

    token_budget_hit = False
    for job in new_jobs:
        if run_log.tokens_used >= settings.RADAR_TOKEN_BUDGET_PER_ROUND:
            token_budget_hit = True
            break
        run_log.tokens_used += _process_with_retry(job, run_log)
        run_log.jobs_scored += 1

    if token_budget_hit:
        run_log.errors.append({"error": "Teto de tokens da rodada atingido — RF-05.4."})
        notify_failure(f"Rodada {slot}: teto de tokens atingido, vagas restantes ficaram sem score.")

    tier_promotion.evaluate_promotions()
    tier_promotion.revert_expired_promotions()

    ready_jobs = [j for j in new_jobs if j.status in (Job.Status.RADAR, Job.Status.DOSSIER_PENDING)]
    notify_round_summary(run_log, ready_jobs)
    for job in ready_jobs:
        if job.company.tier == HIGH_PRIORITY_TIER and (job.recruiter_score or 0) >= HIGH_PRIORITY_RECRUITER_SCORE:
            notify_high_priority_job(job)

    try:
        sheets_sync.sync_all(run_log)
    except Exception as exc:  # noqa: BLE001 — não derruba a rodada (RF-13.5)
        run_log.errors.append({"error": f"Falha ao sincronizar planilha: {exc}"})
        notify_failure(f"Rodada {slot}: falha ao sincronizar Google Sheets — {exc}")

    run_log.finished_at = timezone.now()
    run_log.status = (
        RunLog.Status.COMPLETED_WITH_ERRORS if run_log.errors else RunLog.Status.COMPLETED
    )
    run_log.save()

    return {
        "run_log_id": run_log.pk,
        "companies_polled": run_log.companies_polled,
        "jobs_found": run_log.jobs_found,
        "jobs_scored": run_log.jobs_scored,
        "status": run_log.status,
    }
