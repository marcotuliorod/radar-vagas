from django.contrib import admin

from .models import Company, Job, RunLog


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "tier", "ats_provider", "poll_error_count", "last_polled_at")
    list_filter = ("tier", "ats_provider")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "status",
        "score",
        "recruiter_score",
        "published_at",
        "first_seen_at",
    )
    list_filter = ("status", "source", "company__tier")
    search_fields = ("title", "company__name", "external_id")


@admin.register(RunLog)
class RunLogAdmin(admin.ModelAdmin):
    list_display = (
        "scheduled_slot",
        "started_at",
        "finished_at",
        "mode",
        "status",
        "companies_polled",
        "jobs_found",
        "jobs_scored",
    )
    list_filter = ("scheduled_slot", "mode", "status")
