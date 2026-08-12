"""Promoção automática de tier — RF-02.4: empresa que publica ≥3 vagas em 7
dias sobe um tier por 30 dias; passado esse prazo, volta ao tier original."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from radar.models import Company


def evaluate_promotions() -> list[Company]:
    window_start = timezone.now() - timedelta(days=settings.RADAR_TIER_PROMOTION_WINDOW_DAYS)
    candidates = (
        Company.objects.exclude(tier=Company.Tier.A)
        .filter(auto_promoted_at__isnull=True)
        .annotate(
            recent_jobs=Count("jobs", filter=Q(jobs__first_seen_at__gte=window_start))
        )
        .filter(recent_jobs__gte=settings.RADAR_TIER_PROMOTION_MIN_JOBS)
    )

    promoted = []
    for company in candidates:
        company.tier = Company.Tier.A if company.tier == Company.Tier.B else Company.Tier.B
        company.auto_promoted_at = timezone.now()
        company.save(update_fields=["tier", "auto_promoted_at"])
        promoted.append(company)
    return promoted


def revert_expired_promotions() -> list[Company]:
    cutoff = timezone.now() - timedelta(days=settings.RADAR_TIER_PROMOTION_DURATION_DAYS)
    expired = Company.objects.filter(auto_promoted_at__isnull=False, auto_promoted_at__lte=cutoff)

    reverted = []
    for company in expired:
        company.tier = Company.Tier.C if company.tier == Company.Tier.B else Company.Tier.B
        company.auto_promoted_at = None
        company.save(update_fields=["tier", "auto_promoted_at"])
        reverted.append(company)
    return reverted
