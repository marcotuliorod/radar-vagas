from radar.intelligence import boolean_string, brief, knockouts, scoring
from radar.models import Job


class FakeLLMResponse:
    def __init__(self, data: dict, input_tokens: int = 100, output_tokens: int = 50):
        self.data = data
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _make_job(make_company, **overrides):
    company = make_company()
    defaults = dict(
        company=company,
        external_id="ext-1",
        title="Product Owner Sênior",
        location="São Paulo",
        description_raw="Vaga de Product Owner Sênior para squad de pagamentos.",
        source=Job.Source.GREENHOUSE,
    )
    defaults.update(overrides)
    return Job.objects.create(**defaults)


def test_reconstruct_brief_stores_result_in_requirements(make_company, monkeypatch):
    job = _make_job(make_company)
    fake_brief = {"perfil_alvo": "PO sênior fintech", "must_haves_inegociaveis": ["backlog"]}
    monkeypatch.setattr(brief, "call_haiku", lambda prompt: FakeLLMResponse(fake_brief))

    result = brief.reconstruct_brief(job)

    assert result == fake_brief
    assert job.requirements["brief"] == fake_brief


def test_detect_knockouts_and_apply_rejected(make_company, monkeypatch):
    job = _make_job(make_company)
    payload = {
        "knockouts": [
            {
                "criterio": "Anos mínimos de experiência",
                "valor_exigido": "10 anos em fintech",
                "valor_do_candidato": "desconhecido",
                "atendido": "false",
                "eliminatorio_real": True,
                "observacao": "",
            }
        ],
        "veredito": "reprovado",
    }
    monkeypatch.setattr(knockouts, "call_haiku", lambda prompt: FakeLLMResponse(payload))

    result = knockouts.detect_knockouts(job, brief={})
    rejected = knockouts.apply_knockout_result(job, result)

    assert rejected is True
    assert job.status == Job.Status.REJECTED
    assert "Anos mínimos" in job.rejection_reason
    assert job.knockouts == payload["knockouts"]


def test_detect_knockouts_approved_does_not_reject(make_company, monkeypatch):
    job = _make_job(make_company)
    payload = {"knockouts": [], "veredito": "aprovado"}
    monkeypatch.setattr(knockouts, "call_haiku", lambda prompt: FakeLLMResponse(payload))

    result = knockouts.detect_knockouts(job, brief={})
    rejected = knockouts.apply_knockout_result(job, result)

    assert rejected is False
    assert job.status == Job.Status.NEW


def test_score_job_stays_on_haiku_when_below_escalation_threshold(make_company, monkeypatch):
    job = _make_job(make_company)
    low_score_payload = {
        "score": 40, "score_rationale": "gap de stack",
        "recruiter_score": 30, "recruiter_rationale": "sem fit de senioridade",
        "rejection_reason": "Não atende requisitos obrigatórios de stack.",
        "requisitos_obrigatorios": [], "requisitos_desejaveis": [], "gaps_criticos": ["stack"],
        "senioridade_detectada": "sênior", "banda_percebida_do_candidato": "pleno",
        "sinais_de_alerta": [], "recomendacao": "descartar",
    }
    calls = {"sonnet": 0}
    monkeypatch.setattr(scoring, "call_haiku", lambda prompt: FakeLLMResponse(low_score_payload))
    monkeypatch.setattr(scoring, "call_sonnet", lambda prompt: calls.__setitem__("sonnet", calls["sonnet"] + 1) or FakeLLMResponse({}))

    scoring.score_job(job, brief={})

    assert calls["sonnet"] == 0
    assert job.status == Job.Status.RADAR
    assert job.rejection_reason == low_score_payload["rejection_reason"]


def test_score_job_escalates_to_sonnet_above_threshold(make_company, monkeypatch):
    job = _make_job(make_company)
    preliminary_payload = {"score": 80, "recruiter_score": 60}
    detailed_payload = {
        "score": 85, "score_rationale": "forte aderência",
        "recruiter_score": 90, "recruiter_rationale": "entraria na shortlist",
        "rejection_reason": "", "requisitos_obrigatorios": [], "requisitos_desejaveis": [],
        "gaps_criticos": [], "senioridade_detectada": "sênior",
        "banda_percebida_do_candidato": "sênior", "sinais_de_alerta": [],
        "recomendacao": "gerar_dossie",
    }
    monkeypatch.setattr(scoring, "call_haiku", lambda prompt: FakeLLMResponse(preliminary_payload))
    monkeypatch.setattr(scoring, "call_sonnet", lambda prompt: FakeLLMResponse(detailed_payload))

    scoring.score_job(job, brief={})

    assert job.score == 85
    assert job.recruiter_score == 90
    assert job.status == Job.Status.DOSSIER_PENDING


def test_generate_boolean_string_stores_value(make_company, monkeypatch):
    job = _make_job(make_company)
    payload = {"boolean_string": '("Product Owner" OR "PO") AND fintech', "titulos_alvo": ["Product Owner"]}
    monkeypatch.setattr(boolean_string, "call_haiku", lambda prompt: FakeLLMResponse(payload))

    result, tokens = boolean_string.generate_boolean_string(job)

    assert result == payload
    assert job.boolean_string == payload["boolean_string"]
    assert tokens == 150
