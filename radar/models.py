"""
Modelo de dados do Radar — §8 do PRD, restrito ao escopo das Fases 0-2:
watchlist (Company), vagas coletadas + inteligência (Job) e execuções
autônomas (RunLog). As tabelas `dossier`, `contact` e `event_log` são de
fases posteriores (geração de CV, vitrine inbound, auditoria de documento) e
não existem aqui.
"""

from django.db import models


class Company(models.Model):
    """Empresa monitorada — RF-02."""

    class Tier(models.TextChoices):
        A = "A", "A"
        B = "B", "B"
        C = "C", "C"

    class AtsProvider(models.TextChoices):
        GREENHOUSE = "greenhouse", "Greenhouse"
        LEVER = "lever", "Lever"
        ASHBY = "ashby", "Ashby"
        GUPY = "gupy", "Gupy"
        OUTRO = "outro", "Outro / desconhecido"

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    ats_provider = models.CharField(
        max_length=20, choices=AtsProvider.choices, default=AtsProvider.OUTRO
    )
    ats_board_url = models.URLField(
        blank=True,
        help_text="URL/identificador do board no ATS (ex.: token do Greenhouse/Lever/Ashby).",
    )
    tier = models.CharField(max_length=1, choices=Tier.choices)
    auto_promoted_at = models.DateTimeField(
        null=True, blank=True, help_text="RF-02.4 — promoção automática de tier (válida por 30 dias)."
    )
    careers_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    last_polled_at = models.DateTimeField(null=True, blank=True)
    poll_error_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tier", "name"]
        verbose_name_plural = "companies"

    def __str__(self) -> str:
        return f"{self.name} (tier {self.tier})"


class RunLog(models.Model):
    """Execução autônoma de uma rodada — RF-13/RF-14."""

    class Slot(models.TextChoices):
        R1 = "R1", "R1"
        R2 = "R2", "R2"
        R3 = "R3", "R3"
        R4 = "R4", "R4"

    class Mode(models.TextChoices):
        NORMAL = "normal", "Normal"
        BACKLOG = "backlog", "Backlog (segunda-feira)"
        REDUZIDO = "reduzido", "Reduzido (fim de semana)"

    class Status(models.TextChoices):
        RUNNING = "running", "Em execução"
        COMPLETED = "completed", "Concluída"
        COMPLETED_WITH_ERRORS = "completed_with_errors", "Concluída com erros"
        FAILED = "failed", "Falhou"

    scheduled_slot = models.CharField(max_length=2, choices=Slot.choices)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.NORMAL)
    companies_polled = models.PositiveIntegerField(default=0)
    jobs_found = models.PositiveIntegerField(default=0)
    jobs_scored = models.PositiveIntegerField(default=0)
    dossiers_generated = models.PositiveIntegerField(
        default=0, help_text="Sempre 0 nesta fase — geração de dossiê é Fase 3."
    )
    dossiers_failed = models.PositiveIntegerField(default=0)
    tokens_used = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.RUNNING)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.scheduled_slot} {self.started_at:%Y-%m-%d %H:%M} ({self.status})"


class Job(models.Model):
    """Vaga detectada, com campos de coleta (RF-03) e inteligência (RF-04/RF-11)."""

    class Source(models.TextChoices):
        GREENHOUSE = "greenhouse", "Greenhouse"
        LEVER = "lever", "Lever"
        ASHBY = "ashby", "Ashby"
        GUPY = "gupy", "Gupy"
        INDEED = "indeed", "Indeed"
        MANUAL = "manual", "Manual"

    class Status(models.TextChoices):
        NEW = "new", "Nova"
        RADAR = "radar", "Radar (fit parcial)"
        DOSSIER_PENDING = "dossier_pending", "Aguardando dossiê (Fase 3)"
        REJECTED = "rejected", "Reprovada"
        EXPIRED = "expired", "Expirada"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="jobs")
    external_id = models.CharField(max_length=255)
    title = models.CharField(max_length=500)
    location = models.CharField(max_length=255, blank=True)
    work_model = models.CharField(max_length=100, blank=True)
    seniority = models.CharField(max_length=100, blank=True)
    description_raw = models.TextField(blank=True)
    description_hash = models.CharField(max_length=64, db_index=True, blank=True)
    url_apply = models.URLField(blank=True)
    source = models.CharField(max_length=20, choices=Source.choices)

    published_at = models.DateTimeField(null=True, blank=True)
    published_at_estimated = models.BooleanField(default=False)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    found_in_run = models.ForeignKey(
        RunLog, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs_found_in"
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    # RF-04 — score do candidato para a vaga
    requirements = models.JSONField(default=dict, blank=True)
    score = models.SmallIntegerField(null=True, blank=True)
    score_rationale = models.TextField(blank=True)
    gaps = models.JSONField(default=list, blank=True)

    # RF-11 — perspectiva do recrutador
    recruiter_score = models.SmallIntegerField(null=True, blank=True)
    recruiter_rationale = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    knockouts = models.JSONField(default=list, blank=True)
    boolean_string = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)

    class Meta:
        ordering = ["-first_seen_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "external_id"], name="uniq_company_external_id"
            )
        ]
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"{self.title} — {self.company.name}"
