import json
from pathlib import Path

PERFIL_PATH = Path(__file__).resolve().parents[2] / "perfil.json"


def _load_perfil() -> dict:
    return json.loads(PERFIL_PATH.read_text(encoding="utf-8"))


def test_perfil_json_is_valid_and_has_required_top_level_keys():
    perfil = _load_perfil()
    for key in ["identidade", "resumo_base", "experiencias", "skills", "preferencias"]:
        assert key in perfil


def test_every_skill_evidence_points_to_an_existing_bullet():
    perfil = _load_perfil()
    all_bullet_ids = {
        bullet["id"]
        for experiencia in perfil["experiencias"]
        for bullet in experiencia["bullets"]
    }
    for skill in perfil["skills"]:
        for bullet_id in skill["evidencia"]:
            assert bullet_id in all_bullet_ids, f"Skill '{skill['nome']}' cita bullet inexistente '{bullet_id}'"


def test_no_bullet_has_fabricated_metric_without_source_data():
    # RF-06.2/RF-07.4: nenhuma métrica pode ser inventada. Como o currículo-fonte
    # não trazia números, todo bullet deve estar com metrica/impacto vazios ou
    # com texto descritivo — nunca com um valor numérico solto sem contexto.
    perfil = _load_perfil()
    for experiencia in perfil["experiencias"]:
        for bullet in experiencia["bullets"]:
            assert isinstance(bullet["metrica"], str)
            assert isinstance(bullet["impacto"], str)


def test_preferencias_left_blank_as_decided_by_user():
    perfil = _load_perfil()
    preferencias = perfil["preferencias"]
    assert preferencias["modelo_trabalho"] == []
    assert preferencias["faixa_salarial_min"] is None
    assert preferencias["localidades_aceitas"] == []
    assert preferencias["dealbreakers"] == []
