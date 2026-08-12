from datetime import datetime

from django.utils import timezone

from radar.models import RunLog
from radar.tasks import determine_mode
from radarvagas.celery import app as celery_app


def test_beat_schedule_matches_anexo_g():
    schedule = celery_app.conf.beat_schedule

    assert set(schedule.keys()) == {
        "radar-r1-madrugada", "radar-r2-manha", "radar-r3-tarde", "radar-r4-fim-do-dia",
    }

    r1 = schedule["radar-r1-madrugada"]
    assert r1["kwargs"] == {"slot": "R1", "tiers": ["A", "B", "C"]}
    assert r1["schedule"].hour == {6}
    assert r1["schedule"].minute == {0}
    # R1 não tem restrição de dia da semana (roda todo dia — RF-14.4)
    assert r1["schedule"].day_of_week == set(range(7))

    for name, hour, minute, tiers in [
        ("radar-r2-manha", 10, 0, ["A", "B"]),
        ("radar-r3-tarde", 14, 0, ["A", "B"]),
        ("radar-r4-fim-do-dia", 18, 30, ["A", "B"]),
    ]:
        entry = schedule[name]
        assert entry["kwargs"] == {"slot": entry["kwargs"]["slot"], "tiers": tiers}
        assert entry["schedule"].hour == {hour}
        assert entry["schedule"].minute == {minute}
        # dias úteis: segunda(1) a sexta(5) no formato crontab do Celery
        assert entry["schedule"].day_of_week == {1, 2, 3, 4, 5}


def _monday_morning():
    return timezone.make_aware(datetime(2026, 8, 10, 6, 0))  # 10/ago/2026 é uma segunda


def _saturday_morning():
    return timezone.make_aware(datetime(2026, 8, 8, 6, 0))


def _wednesday_morning():
    return timezone.make_aware(datetime(2026, 8, 12, 6, 0))


def test_determine_mode_backlog_on_monday(monkeypatch):
    monkeypatch.setattr(timezone, "now", _monday_morning)
    assert determine_mode("R1") == RunLog.Mode.BACKLOG


def test_determine_mode_reduzido_on_weekend(monkeypatch):
    monkeypatch.setattr(timezone, "now", _saturday_morning)
    assert determine_mode("R1") == RunLog.Mode.REDUZIDO


def test_determine_mode_normal_on_weekday(monkeypatch):
    monkeypatch.setattr(timezone, "now", _wednesday_morning)
    assert determine_mode("R1") == RunLog.Mode.NORMAL


def test_determine_mode_always_normal_for_r2_r3_r4(monkeypatch):
    monkeypatch.setattr(timezone, "now", _monday_morning)
    assert determine_mode("R2") == RunLog.Mode.NORMAL
    assert determine_mode("R3") == RunLog.Mode.NORMAL
    assert determine_mode("R4") == RunLog.Mode.NORMAL
