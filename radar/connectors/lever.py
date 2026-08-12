"""
Conector Lever (RF-03.1) — API pública de postings, sem autenticação:
https://github.com/lever/postings-api

`company.ats_board_url` aceita o "site" do Lever (o identificador usado em
https://jobs.lever.co/{site}) ou a URL já resolvida da API.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .base import BaseConnector, ConnectorError, RawJob, get_with_retry

API_URL_TEMPLATE = "https://api.lever.co/v0/postings/{site}"


def _extract_site(ats_board_url: str) -> str:
    url = ats_board_url.strip()
    if not url:
        raise ConnectorError("Company sem ats_board_url configurada para o conector Lever.")
    match = re.search(r"(?:jobs\.lever\.co|api\.lever\.co/v0/postings)/([^/?#]+)", url)
    if match:
        return match.group(1)
    return url.strip("/")


class LeverConnector(BaseConnector):
    provider = "lever"

    def fetch_jobs(self, company) -> list[RawJob]:
        site = _extract_site(company.ats_board_url)
        url = API_URL_TEMPLATE.format(site=site)
        response = get_with_retry(url, params={"mode": "json"})
        postings = response.json()

        raw_jobs: list[RawJob] = []
        for posting in postings:
            categories = posting.get("categories", {}) or {}
            created_at_ms = posting.get("createdAt")
            published_at = (
                datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc)
                if created_at_ms
                else None
            )
            description = posting.get("descriptionPlain") or posting.get("description", "")
            raw_jobs.append(
                RawJob(
                    external_id=str(posting["id"]),
                    title=posting.get("text", ""),
                    location=categories.get("location", ""),
                    work_model=posting.get("workplaceType", ""),
                    description_raw=description,
                    url_apply=posting.get("applyUrl") or posting.get("hostedUrl", ""),
                    source=self.provider,
                    published_at=published_at,
                    published_at_estimated=published_at is None,
                )
            )
        return raw_jobs
