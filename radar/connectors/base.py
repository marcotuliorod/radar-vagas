"""
Interface comum dos conectores de ATS (RF-03.1). Cada conector implementa
`fetch_jobs(company)` e devolve uma lista de `RawJob` normalizados. Todas as
chamadas passam por `get_with_retry`, que aplica timeout, retry e backoff
exponencial (RNF-05) e loga (sem levantar) erros de rede — quem decide o que
fazer com uma falha isolada é a camada de orquestração (RF-13.5: falha de
uma fonte nunca derruba a rodada inteira).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 2


@dataclass(frozen=True)
class RawJob:
    """Vaga normalizada, antes de virar `radar.models.Job`."""

    external_id: str
    title: str
    location: str
    description_raw: str
    url_apply: str
    source: str
    work_model: str = ""
    published_at: Optional[datetime] = None
    published_at_estimated: bool = False


class ConnectorError(Exception):
    """Falha ao consultar um ATS — capturada e registrada pelo chamador."""


def get_with_retry(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
) -> requests.Response:
    """GET com timeout + retry + backoff exponencial. Só aceita endpoints
    públicos de leitura (RF-03.6) — nenhum conector deve autenticar como
    usuário nem raspar páginas que exijam login."""

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            if response.status_code == 429 or response.status_code >= 500:
                raise ConnectorError(f"{response.status_code} de {url}")
            response.raise_for_status()
            return response
        except (requests.RequestException, ConnectorError) as exc:
            last_error = exc
            if attempt == max_retries:
                break
            sleep_for = backoff_base_seconds * (2 ** (attempt - 1))
            logger.warning(
                "Falha ao consultar %s (tentativa %s/%s): %s — nova tentativa em %ss",
                url, attempt, max_retries, exc, sleep_for,
            )
            time.sleep(sleep_for)

    raise ConnectorError(f"Falha ao consultar {url} após {max_retries} tentativas: {last_error}")


class BaseConnector:
    provider: str = "outro"

    def fetch_jobs(self, company) -> list[RawJob]:
        raise NotImplementedError
