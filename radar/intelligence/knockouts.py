"""Detecção de knockouts — RF-11.4 (Anexo C do PRD). Corta a vaga antes das
etapas caras (score, boolean string) quando reprovada, economizando custo."""

from __future__ import annotations

import json

from radar.intelligence.llm_client import call_haiku, truncate
from radar.models import Job

PROMPT_TEMPLATE = """\
Liste os critérios eliminatórios que o ATS desta vaga aplicaria ANTES de
qualquer leitura humana, e avalie cada um contra o perfil do candidato
(fornecido no contexto do sistema).

VAGA:
Título: {title}
Empresa: {company}
Localização: {location}
Modelo de trabalho: {work_model}
Descrição:
{description}

BRIEF RECONSTRUÍDO:
{brief}

Considere: anos mínimos de experiência, localidade e autorização de
trabalho, idioma exigido e nível, formação obrigatória, certificação
obrigatória, disponibilidade, modelo de trabalho, pretensão salarial.

Marque "desconhecido" quando o perfil não permitir concluir — nunca
presuma a favor do candidato.

Responda SOMENTE em JSON:
{{
  "knockouts": [
    {{
      "criterio": "",
      "valor_exigido": "",
      "valor_do_candidato": "",
      "atendido": "true | false | desconhecido",
      "eliminatorio_real": true,
      "observacao": ""
    }}
  ],
  "veredito": "aprovado | reprovado | requer_confirmacao"
}}
"""


def detect_knockouts(job: Job, brief: dict) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        title=job.title,
        company=job.company.name,
        location=job.location,
        work_model=job.work_model,
        description=truncate(job.description_raw),
        brief=json.dumps(brief, ensure_ascii=False),
    )
    response = call_haiku(prompt)
    job.knockouts = response.data.get("knockouts", [])
    return response.data


def apply_knockout_result(job: Job, result: dict) -> bool:
    """Aplica o veredito ao Job. Retorna True se a vaga foi reprovada (RF-11.4:
    encerra o processamento aqui, sem gastar com score/boolean string)."""

    veredito = result.get("veredito")
    if veredito == "reprovado":
        job.status = Job.Status.REJECTED
        reprovados = [
            k for k in result.get("knockouts", [])
            if k.get("eliminatorio_real") and k.get("atendido") == "false"
        ]
        if reprovados:
            criterio = reprovados[0]
            job.rejection_reason = (
                f"Knockout reprovado: {criterio.get('criterio')} "
                f"(exigido: {criterio.get('valor_exigido')}; "
                f"candidato: {criterio.get('valor_do_candidato')})"
            )
        else:
            job.rejection_reason = "Knockout reprovado pelo ATS."
        return True
    return False
