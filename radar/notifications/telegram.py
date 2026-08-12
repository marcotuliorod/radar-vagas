"""Notificação pós-rodada via Telegram Bot API — RF-10."""

from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_URL_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"


def _send(text: str) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        logger.info("Telegram não configurado — mensagem suprimida: %s", text)
        return False

    try:
        response = requests.post(
            API_URL_TEMPLATE.format(token=token),
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        logger.exception("Falha ao enviar notificação Telegram.")
        return False


def notify_round_summary(run_log, ready_jobs: list) -> bool:
    """RF-10.1 — resumo pós-rodada. RF-10.2 — rodada sem novidade não notifica."""
    if not ready_jobs:
        return False

    lines = [f"*Radar — rodada {run_log.scheduled_slot}* ({len(ready_jobs)} vaga(s) nova(s))"]
    for job in ready_jobs:
        lines.append(
            f"• {job.company.name} — {job.title} "
            f"(score {job.score} / recrutador {job.recruiter_score}) — {job.url_apply}"
        )
    return _send("\n".join(lines))


def notify_high_priority_job(job) -> bool:
    """RF-10.3 — alerta imediato para Tier A com recruiter_score ≥ 85."""
    text = (
        f"🎯 *Vaga prioritária* — {job.company.name} ({job.company.tier}) — {job.title}\n"
        f"recruiter_score={job.recruiter_score}\n{job.url_apply}"
    )
    return _send(text)


def notify_failure(message: str) -> bool:
    """RF-10.4 — alerta de falha (rodada não concluída, poll quebrado, teto de tokens)."""
    return _send(f"⚠️ *Radar — falha*\n{message}")
