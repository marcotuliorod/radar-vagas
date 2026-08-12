"""
Sincronização Postgres → Google Sheets ao fim de cada rodada — RF-09. A
planilha é uma *view*: o banco é a fonte de verdade (§4.6 do PRD). A única
coluna que a planilha devolve ao sistema é `status manual` (RF-09.4) — isso
fica fora de escopo nesta fase (exigiria um passo de leitura antes de cada
rodada; não implementado aqui).

Abas `Dossiês prontos` e `Reprovados no gate` existem só com cabeçalho: são
alimentadas na Fase 3 (geração de CV + gate de qualidade), fora de escopo.
"""

from __future__ import annotations

import logging

import gspread
from django.conf import settings

from radar.models import Company, Job, RunLog

logger = logging.getLogger(__name__)

TAB_WATCHLIST = "Watchlist"
TAB_RADAR = "Radar"
TAB_RODADAS = "Rodadas"
TAB_METRICAS = "Métricas"
TAB_DOSSIES_PRONTOS = "Dossiês prontos"
TAB_REPROVADOS_NO_GATE = "Reprovados no gate"

RADAR_HEADERS = [
    "empresa", "cargo", "tier", "fonte", "link", "publicada em", "detectada em",
    "TTR (h)", "score", "recruiter_score", "veredito da triagem",
    "motivo provável de descarte", "knockouts", "gate", "link do dossiê",
    "status manual", "aplicada em", "notas",
]
WATCHLIST_HEADERS = ["empresa", "tier", "ats", "careers_url", "último poll", "erros consecutivos"]
RODADAS_HEADERS = [
    "slot", "início", "fim", "modo", "empresas", "vagas encontradas",
    "vagas scoradas", "tokens", "status",
]
METRICAS_HEADERS = ["métrica", "valor"]


def _get_or_create_worksheet(spreadsheet, title: str, headers: list[str]):
    try:
        worksheet = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(headers))
        worksheet.append_row(headers)
    return worksheet


def _replace_rows(worksheet, headers: list[str], rows: list[list]) -> None:
    worksheet.clear()
    worksheet.append_row(headers)
    if rows:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def _open_spreadsheet():
    if not settings.GOOGLE_SHEETS_CREDENTIALS_PATH or not settings.GOOGLE_SHEETS_SPREADSHEET_ID:
        logger.info("Google Sheets não configurado — sync suprimido.")
        return None
    client = gspread.service_account(filename=settings.GOOGLE_SHEETS_CREDENTIALS_PATH)
    return client.open_by_key(settings.GOOGLE_SHEETS_SPREADSHEET_ID)


def sync_watchlist(spreadsheet) -> None:
    worksheet = _get_or_create_worksheet(spreadsheet, TAB_WATCHLIST, WATCHLIST_HEADERS)
    rows = [
        [
            c.name, c.tier, c.ats_provider, c.careers_url,
            c.last_polled_at.isoformat() if c.last_polled_at else "",
            c.poll_error_count,
        ]
        for c in Company.objects.all().order_by("tier", "name")
    ]
    _replace_rows(worksheet, WATCHLIST_HEADERS, rows)


def sync_radar(spreadsheet) -> None:
    worksheet = _get_or_create_worksheet(spreadsheet, TAB_RADAR, RADAR_HEADERS)
    jobs = (
        Job.objects.select_related("company")
        .filter(status__in=[Job.Status.RADAR, Job.Status.DOSSIER_PENDING])
        .order_by("-score")
    )
    rows = [
        [
            job.company.name, job.title, job.company.tier, job.source, job.url_apply,
            job.published_at.isoformat() if job.published_at else "",
            job.first_seen_at.isoformat() if job.first_seen_at else "",
            "",  # TTR — só existe a partir da Fase 3 (dossier.ready_at)
            job.score or "", job.recruiter_score or "",
            "",  # veredito da triagem — Fase 3
            job.rejection_reason, len(job.knockouts or []),
            "",  # gate — Fase 3
            "",  # link do dossiê — Fase 3
            "pending", "", "",
        ]
        for job in jobs
    ]
    _replace_rows(worksheet, RADAR_HEADERS, rows)


def sync_rodadas(spreadsheet) -> None:
    worksheet = _get_or_create_worksheet(spreadsheet, TAB_RODADAS, RODADAS_HEADERS)
    rows = [
        [
            r.scheduled_slot, r.started_at.isoformat(),
            r.finished_at.isoformat() if r.finished_at else "",
            r.mode, r.companies_polled, r.jobs_found, r.jobs_scored, r.tokens_used, r.status,
        ]
        for r in RunLog.objects.order_by("-started_at")[:100]
    ]
    _replace_rows(worksheet, RODADAS_HEADERS, rows)


def sync_metricas(spreadsheet) -> None:
    worksheet = _get_or_create_worksheet(spreadsheet, TAB_METRICAS, METRICAS_HEADERS)
    total_jobs = Job.objects.count()
    rows = [
        ["empresas na watchlist", Company.objects.count()],
        ["vagas totais coletadas", total_jobs],
        ["vagas em radar", Job.objects.filter(status=Job.Status.RADAR).count()],
        ["vagas aguardando dossiê (Fase 3)", Job.objects.filter(status=Job.Status.DOSSIER_PENDING).count()],
        ["vagas reprovadas em knockout", Job.objects.filter(status=Job.Status.REJECTED).count()],
        ["rodadas registradas", RunLog.objects.count()],
    ]
    _replace_rows(worksheet, METRICAS_HEADERS, rows)


def sync_all(run_log: RunLog) -> bool:
    spreadsheet = _open_spreadsheet()
    if spreadsheet is None:
        return False

    _get_or_create_worksheet(spreadsheet, TAB_DOSSIES_PRONTOS, RADAR_HEADERS)
    _get_or_create_worksheet(spreadsheet, TAB_REPROVADOS_NO_GATE, RADAR_HEADERS)
    sync_watchlist(spreadsheet)
    sync_radar(spreadsheet)
    sync_rodadas(spreadsheet)
    sync_metricas(spreadsheet)
    return True
