"""
Conector Gupy (RF-03.1) — ATS mais usado no Brasil (confirmado pelo
relatório de mercado anexado ao PRD: plataforma de recrutamento mais
acessada do país). Diferente de Greenhouse/Lever/Ashby, a Gupy não publica
uma especificação oficial e estável de API pública — cada tenant expõe seu
board em `https://{empresa}.gupy.io` e o endpoint JSON por trás dele varia.

Por isso, `company.ats_board_url` aqui é a URL *completa* do endpoint de
listagem de vagas (ex.: algo como
`https://{empresa}.gupy.io/api/job_postings?jobBoardSource=gupy_public_page`),
não um token — valide o endpoint real do tenant antes de usar em produção
e ajuste `_normalize_job` se os nomes de campo divergirem do que está
mapeado abaixo.
"""

from __future__ import annotations

from datetime import datetime

from .base import BaseConnector, ConnectorError, RawJob, get_with_retry


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _first(job: dict, *keys, default=""):
    for key in keys:
        if key in job and job[key] not in (None, ""):
            return job[key]
    return default


def _normalize_job(job: dict) -> RawJob:
    location = job.get("location") or {}
    if isinstance(location, dict):
        location_str = ", ".join(
            filter(None, [location.get("city"), location.get("state"), location.get("country")])
        )
    else:
        location_str = str(location)

    published_at = _parse_datetime(_first(job, "publishedDate", "createdDate", "publishedAt"))

    return RawJob(
        external_id=str(_first(job, "id", "externalId", "careerPageId")),
        title=_first(job, "name", "title"),
        location=location_str,
        work_model=_first(job, "type", "workplaceType"),
        description_raw=_first(job, "description", "careerPageDescription"),
        url_apply=_first(job, "careerPageUrl", "jobUrl", "url"),
        source="gupy",
        published_at=published_at,
        published_at_estimated=published_at is None,
    )


class GupyConnector(BaseConnector):
    provider = "gupy"

    def fetch_jobs(self, company) -> list[RawJob]:
        url = company.ats_board_url.strip()
        if not url:
            raise ConnectorError("Company sem ats_board_url (endpoint Gupy) configurada.")
        response = get_with_retry(url)
        payload = response.json()

        if isinstance(payload, list):
            jobs = payload
        else:
            jobs = (
                payload.get("data")
                or payload.get("results")
                or payload.get("jobPostings")
                or []
            )

        return [_normalize_job(job) for job in jobs]
