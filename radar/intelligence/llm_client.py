"""
Cliente fino sobre o SDK `anthropic` — roteamento por tarefa conforme §12 do
PRD (Haiku para parsing/brief/knockouts/score preliminar/boolean string,
Sonnet só para score detalhado quando o preliminar ≥ 75) e prompt caching
da persona (Anexo D) + `perfil.json`, que são idênticos em toda chamada.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

MAX_DESCRIPTION_CHARS = 6000


@lru_cache(maxsize=1)
def load_persona() -> str:
    return Path(settings.RADAR_PERSONA_PATH).read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_perfil_json() -> str:
    return Path(settings.RADAR_PERFIL_PATH).read_text(encoding="utf-8")


def truncate(text: str, max_chars: int = MAX_DESCRIPTION_CHARS) -> str:
    """RF-04.1/§12 — truncar descrições longas antes do parsing (custo de token)."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[...descrição truncada...]"


_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


class LLMResponse:
    def __init__(self, data: dict, input_tokens: int, output_tokens: int):
        self.data = data
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Resposta do modelo não é JSON válido: {text[:500]!r}") from exc


def call_model(*, model: str, user_prompt: str, max_tokens: int = 1500) -> LLMResponse:
    """Envia persona + perfil.json cacheados no `system`, e o prompt específico
    da tarefa (Anexos B/C/E/F) como turno do usuário. Espera resposta SOMENTE
    em JSON — como todos os prompts do PRD exigem."""

    system_blocks = [
        {"type": "text", "text": load_persona(), "cache_control": {"type": "ephemeral"}},
        {
            "type": "text",
            "text": f"PERFIL (perfil.json do candidato):\n{load_perfil_json()}",
            "cache_control": {"type": "ephemeral"},
        },
    ]

    response = get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_blocks,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    data = _parse_json(text)
    return LLMResponse(
        data=data,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def call_haiku(user_prompt: str, *, max_tokens: int = 1500) -> LLMResponse:
    return call_model(model=settings.ANTHROPIC_MODEL_HAIKU, user_prompt=user_prompt, max_tokens=max_tokens)


def call_sonnet(user_prompt: str, *, max_tokens: int = 2000) -> LLMResponse:
    return call_model(model=settings.ANTHROPIC_MODEL_SONNET, user_prompt=user_prompt, max_tokens=max_tokens)
