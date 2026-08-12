"""
Conector Ashby (RF-03.1) — API pública de job board, sem autenticação:
https://developers.ashbyhq.com/reference/jobpostingapi

`company.ats_board_url` aceita o nome do job board Ashby (o identificador
usado em https://jobs.ashbyhq.com/{nome}) ou a URL já resolvida da API.
"""

from __future__ import annotations

import re
from datetime import datetime

from .base import BaseConnector, ConnectorError, RawJob, get_with_retry

API_URL_TEMPLATE = "https://api.ashbyhq.com/posting-api/job-board/{board_name}"


def _extract_board_name(ats_board_url: str) -> str:
    url = ats_board_url.strip()
    if not url:
        raise ConnectorError("Company sem ats_board_url configurada para o conector Ashby.")
    match = re.search(r"(?:jobs\.ashbyhq\.com|posting-api/job-board)/([^/?#]+)", url)
    if match:
        return match.group(1)
    return url.strip("/")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class AshbyConnector(BaseConnector):
    provider = "ashby"

    def fetch_jobs(self, company) -> list[RawJob]:
        board_name = _extract_board_name(company.ats_board_url)
        url = API_URL_TEMPLATE.format(board_name=board_name)
        response = get_with_retry(url, params={"includeCompensation": "false"})
        payload = response.json()

        raw_jobs: list[RawJob] = []
        for job in payload.get("jobs", []):
            published_at = _parse_datetime(job.get("publishedAt"))
            raw_jobs.append(
                RawJob(
                    external_id=str(job["id"]),
                    title=job.get("title", ""),
                    location=job.get("location", ""),
                    work_model="remoto" if job.get("isRemote") else "",
                    description_raw=job.get("descriptionPlain", ""),
                    url_apply=job.get("jobUrl", ""),
                    source=self.provider,
                    published_at=published_at,
                    published_at_estimated=published_at is None,
                )
            )
        return raw_jobs
