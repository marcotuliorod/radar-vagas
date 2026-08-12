"""Boolean string reversa — RF-11.3 (Anexo F). Só gerada para vagas que
avançam para `dossier_pending` (§12: 'Boolean string | Haiku | Apenas
dossiês'), já que sourcing reverso só importa quando a vaga é um alvo real."""

from __future__ import annotations

from radar.intelligence.llm_client import call_haiku, truncate
from radar.models import Job

PROMPT_TEMPLATE = """\
Você vai fazer sourcing ativo para esta vaga em uma ferramenta de busca de
candidatos (LinkedIn Recruiter, SeekOut ou similar).

VAGA:
Título: {title}
Empresa: {company}
Descrição:
{description}

Escreva a string booleana que você realmente usaria para encontrar o
candidato ideal. Use o vocabulário corrente do mercado, incluindo
variações em português e inglês, sinônimos de cargo e nomes de
ferramentas como aparecem em currículos reais.

Responda SOMENTE em JSON:
{{
  "boolean_string": "",
  "titulos_alvo": [],
  "skills_obrigatorias_na_busca": [],
  "skills_diferenciais": [],
  "termos_de_exclusao": [],
  "empresas_de_origem_provaveis": []
}}
"""


def generate_boolean_string(job: Job) -> tuple[dict, int]:
    prompt = PROMPT_TEMPLATE.format(
        title=job.title,
        company=job.company.name,
        description=truncate(job.description_raw),
    )
    response = call_haiku(prompt)
    job.boolean_string = response.data.get("boolean_string", "")
    job.requirements = {**(job.requirements or {}), "boolean_string_detalhes": response.data}
    return response.data, response.total_tokens
