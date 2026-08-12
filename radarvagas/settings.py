"""
Settings do Radar — agente de descoberta de vagas.

Fases 0-2 do PRD: perfil canônico, coleta (watchlist + conectores de ATS) e
inteligência (score duplo). Geração de CV/carta, gate de qualidade e Google
Drive (Fase 3+) não fazem parte deste escopo.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "radar",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "radarvagas.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "radarvagas.wsgi.application"

# Sem DATABASE_URL definida, cai em SQLite local — suficiente para rodar
# testes e migrations nesta sessão, que não tem Postgres real disponível.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Celery ---------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
)
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"

# --- Integrações do Radar ---------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL_HAIKU = os.environ.get("ANTHROPIC_MODEL_HAIKU", "claude-haiku-4-5-20251001")
ANTHROPIC_MODEL_SONNET = os.environ.get("ANTHROPIC_MODEL_SONNET", "claude-sonnet-5")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

GOOGLE_SHEETS_CREDENTIALS_PATH = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_PATH", "")
GOOGLE_SHEETS_SPREADSHEET_ID = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "")

RADAR_PERFIL_PATH = os.environ.get("RADAR_PERFIL_PATH", str(BASE_DIR / "perfil.json"))
RADAR_PERSONA_PATH = os.environ.get(
    "RADAR_PERSONA_PATH", str(BASE_DIR / "persona" / "persona_recrutador.md")
)

# Teto de tokens por rodada (RF-05.4) — ao atingir, a rodada degrada para
# "coletar e scorear sem avançar para etapas mais caras" e reporta.
RADAR_TOKEN_BUDGET_PER_ROUND = int(os.environ.get("RADAR_TOKEN_BUDGET_PER_ROUND", "200000"))

# Alerta de empresa com ATS quebrado (RF-02.5)
RADAR_MAX_POLL_ERRORS = int(os.environ.get("RADAR_MAX_POLL_ERRORS", "5"))

# Promoção automática de tier (RF-02.4)
RADAR_TIER_PROMOTION_MIN_JOBS = int(os.environ.get("RADAR_TIER_PROMOTION_MIN_JOBS", "3"))
RADAR_TIER_PROMOTION_WINDOW_DAYS = int(os.environ.get("RADAR_TIER_PROMOTION_WINDOW_DAYS", "7"))
RADAR_TIER_PROMOTION_DURATION_DAYS = int(os.environ.get("RADAR_TIER_PROMOTION_DURATION_DAYS", "30"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}
