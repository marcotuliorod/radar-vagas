"""Score duplo — RF-04.6/RF-04.7 (Anexo B do PRD). `score` = a vaga serve
para o candidato; `recruiter_score` = o candidato entraria na shortlist —
independentes. Score preliminar em Haiku; Sonnet reavalia só quando o
preliminar ≥ 75 (§12), e o resultado do Sonnet substitui o do Haiku."""

from __future__ import annotations

import json

from django.conf import settings

from radar.intelligence.llm_client import LLMResponse, call_haiku, call_sonnet, truncate
from radar.models import Job

PROMPT_TEMPLATE = """\
VAGA:
Título: {title}
Empresa: {company}
Localização: {location}
Modelo de trabalho: {work_model}
Descrição:
{description}

BRIEF RECONSTRUÍDO:
{brief}

PESOS: requisitos obrigatórios 40%, stack/domínio 20%, senioridade 15%,
modelo/localidade 15%, tier da empresa 10%.

Regras:
- Considere apenas evidências presentes no perfil (fornecido no contexto do
  sistema). Ausência de menção = ausência da skill.
- Não presuma senioridade a partir de tempo total de carreira.
- Gaps devem ser específicos e acionáveis.
- Os dois scores são independentes: um pode ser alto e o outro baixo.

Responda SOMENTE em JSON:
{{
  "score": 0,
  "score_rationale": "",
  "recruiter_score": 0,
  "recruiter_rationale": "",
  "rejection_reason": "",
  "requisitos_obrigatorios": [{{"item": "", "coberto": true, "evidencia": ""}}],
  "requisitos_desejaveis": [{{"item": "", "coberto": false}}],
  "gaps_criticos": [],
  "senioridade_detectada": "",
  "banda_percebida_do_candidato": "",
  "sinais_de_alerta": [],
  "recomendacao": "gerar_dossie | radar | descartar"
}}
"""

SONNET_ESCALATION_THRESHOLD = 75
DUAL_SCORE_THRESHOLD = 70


def _build_prompt(job: Job, brief: dict) -> str:
    return PROMPT_TEMPLATE.format(
        title=job.title,
        company=job.company.name,
        location=job.location,
        work_model=job.work_model,
        description=truncate(job.description_raw),
        brief=json.dumps(brief, ensure_ascii=False),
    )


def score_job(job: Job, brief: dict) -> tuple[dict, int]:
    """Executa o score duplo (com escalonamento Haiku→Sonnet) e aplica o
    resultado ao Job. Retorna (payload_bruto, tokens_usados_no_total)."""

    prompt = _build_prompt(job, brief)
    preliminary: LLMResponse = call_haiku(prompt)
    tokens_used = preliminary.total_tokens
    result = preliminary.data

    if (result.get("score") or 0) >= SONNET_ESCALATION_THRESHOLD:
        detailed: LLMResponse = call_sonnet(prompt)
        tokens_used += detailed.total_tokens
        result = detailed.data

    _apply_score(job, result)
    return result, tokens_used


def _apply_score(job: Job, result: dict) -> None:
    job.score = result.get("score")
    job.score_rationale = result.get("score_rationale", "")
    job.recruiter_score = result.get("recruiter_score")
    job.recruiter_rationale = result.get("recruiter_rationale", "")
    job.gaps = result.get("gaps_criticos", [])
    job.requirements = {
        **(job.requirements or {}),
        "requisitos_obrigatorios": result.get("requisitos_obrigatorios", []),
        "requisitos_desejaveis": result.get("requisitos_desejaveis", []),
        "senioridade_detectada": result.get("senioridade_detectada", ""),
        "banda_percebida_do_candidato": result.get("banda_percebida_do_candidato", ""),
        "sinais_de_alerta": result.get("sinais_de_alerta", []),
    }

    passes_both = (
        (job.score or 0) >= DUAL_SCORE_THRESHOLD
        and (job.recruiter_score or 0) >= DUAL_SCORE_THRESHOLD
    )
    if passes_both:
        job.status = Job.Status.DOSSIER_PENDING
    else:
        job.status = Job.Status.RADAR
        # RF-04.8 — se o sistema não formula um motivo plausível, o score está inflado.
        job.rejection_reason = result.get("rejection_reason", "") or (
            "Score abaixo do corte, sem motivo de descarte explícito no retorno do modelo — revisar."
        )
