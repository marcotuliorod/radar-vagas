"""
Configuração do Celery + agendamento das 4 rodadas autônomas (§7 do PRD).

R1 roda todo dia às 06:00 (Brasília) e cobre os tiers A+B+C; como não tem
restrição de dia da semana, ela também é a única rodada de sábado/domingo
(RF-14.4) e a que entra em modo backlog às segundas (RF-14.3) — ambos
detectados em tempo de execução por `radar.tasks.determine_mode`, não por
schedules separados. R2/R3/R4 rodam só em dias úteis.
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "radarvagas.settings")

app = Celery("radarvagas")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "radar-r1-madrugada": {
        "task": "radar.tasks.executar_rodada",
        "schedule": crontab(hour=6, minute=0),
        "kwargs": {"slot": "R1", "tiers": ["A", "B", "C"]},
    },
    "radar-r2-manha": {
        "task": "radar.tasks.executar_rodada",
        "schedule": crontab(hour=10, minute=0, day_of_week="mon-fri"),
        "kwargs": {"slot": "R2", "tiers": ["A", "B"]},
    },
    "radar-r3-tarde": {
        "task": "radar.tasks.executar_rodada",
        "schedule": crontab(hour=14, minute=0, day_of_week="mon-fri"),
        "kwargs": {"slot": "R3", "tiers": ["A", "B"]},
    },
    "radar-r4-fim-do-dia": {
        "task": "radar.tasks.executar_rodada",
        "schedule": crontab(hour=18, minute=30, day_of_week="mon-fri"),
        "kwargs": {"slot": "R4", "tiers": ["A", "B"]},
    },
}
