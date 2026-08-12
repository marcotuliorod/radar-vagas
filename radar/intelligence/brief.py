"""Reconstrução do briefing interno do recrutador — RF-11.2. A persona e o
`perfil.json` já vêm no `system` (llm_client); aqui só entra o específico da
vaga. Resultado é salvo em `job.requirements['brief']` (o schema do PRD não
reserva coluna própria para o brief — ele existe só como insumo intermediário
para knockouts/score, então guardamos dentro do JSONB já existente)."""

from __future__ import annotations

from radar.intelligence.llm_client import call_haiku, truncate
from radar.models import Job

PROMPT_TEMPLATE = """\
Reconstrua o briefing interno que o recrutador provavelmente recebeu do
hiring manager para esta vaga. A descrição pública abaixo é uma tradução
imperfeita desse briefing — leia nas entrelinhas.

VAGA:
Título: {title}
Empresa: {company}
Localização: {location}
Modelo de trabalho: {work_model}
Descrição:
{description}

Responda SOMENTE em JSON:
{{
  "perfil_alvo": "",
  "must_haves_inegociaveis": [],
  "senioridade_real": "",
  "faixa_provavel": "",
  "sinal_de_urgencia": ""
}}
"""


def reconstruct_brief(job: Job) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        title=job.title,
        company=job.company.name,
        location=job.location,
        work_model=job.work_model,
        description=truncate(job.description_raw),
    )
    response = call_haiku(prompt)
    job.requirements = {**(job.requirements or {}), "brief": response.data}
    return response.data
