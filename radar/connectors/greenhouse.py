"""
Conector Greenhouse (RF-03.1) — API pública de job board, sem autenticação:
https://developers.greenhouse.io/job-board.html

`company.ats_board_url` aceita qualquer um destes formatos:
- token puro: "minhaempresa"
- página pública: "https://boards.greenhouse.io/minhaempresa"
- URL já resolvida da API: "https://boards-api.greenhouse.io/v1/boards/minhaempresa/jobs"
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .base import BaseConnector, ConnectorError, RawJob, get_with_retry

API_URL_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def _extract_board_token(ats_board_url: str) -> str:
    url = ats_board_url.strip()
    if not url:
        raise ConnectorError("Company sem ats_board_url configurada para o conector Greenhouse.")
    if "boards-api.greenhouse.io" in url:
        match = re.search(r"/boards/([^/]+)/jobs", url)
        if match:
            return match.group(1)
    if "boards.greenhouse.io" in url:
        match = re.search(r"boards\.greenhouse\.io/([^/?#]+)", url)
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


class GreenhouseConnector(BaseConnector):
    provider = "greenhouse"

    def fetch_jobs(self, company) -> list[RawJob]:
        token = _extract_board_token(company.ats_board_url)
        url = API_URL_TEMPLATE.format(token=token)
        response = get_with_retry(url, params={"content": "true"})
        payload = response.json()

        raw_jobs: list[RawJob] = []
        for job in payload.get("jobs", []):
            published_at = _parse_datetime(job.get("first_published"))
            published_at_estimated = published_at is None
            if published_at is None:
                published_at = _parse_datetime(job.get("updated_at")) or datetime.now(timezone.utc)

            location = (job.get("location") or {}).get("name", "")
            raw_jobs.append(
                RawJob(
                    external_id=str(job["id"]),
                    title=job.get("title", ""),
                    location=location,
                    description_raw=job.get("content", ""),
                    url_apply=job.get("absolute_url", ""),
                    source=self.provider,
                    published_at=published_at,
                    published_at_estimated=published_at_estimated,
                )
            )
        return raw_jobs
