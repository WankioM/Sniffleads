# apps/sources/serializers.py

from rest_framework import serializers
from .models import SiteConfig, CrawlJob, CrawlLog


class SiteConfigSerializer(serializers.ModelSerializer):
    """Full site config serializer."""
    
    class Meta:
        model = SiteConfig
        fields = [
            "id",
            "domain",
            "name",
            "source_type",
            "enabled",
            "start_urls",
            "filters",
            "requests_per_minute",
            "crawl_interval_hours",
            "last_crawl_at",
            "max_pages",
            "follow_links",
            "use_browser",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "last_crawl_at", "created_at", "updated_at"]


class SiteConfigListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views."""
    
    jobs_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SiteConfig
        fields = [
            "id",
            "domain",
            "name",
            "source_type",
            "enabled",
            "last_crawl_at",
            "jobs_count",
        ]
    
    def get_jobs_count(self, obj):
        return obj.crawl_jobs.count()


class CrawlJobSerializer(serializers.ModelSerializer):
    """Full crawl job serializer."""
    
    site_config_name = serializers.CharField(source="site_config.name", read_only=True)
    duration_seconds = serializers.FloatField(read_only=True)
    
    class Meta:
        model = CrawlJob
        fields = [
            "id",
            "site_config",
            "site_config_name",
            "status",
            "scheduled_at",
            "started_at",
            "finished_at",
            "duration_seconds",
            "triggered_by",
            "celery_task_id",
            "stats",
            "error_message",
            "created_at",
        ]
        read_only_fields = [
            "id", "status", "started_at", "finished_at", 
            "celery_task_id", "stats", "error_message", "created_at"
        ]


class CrawlJobListSerializer(serializers.ModelSerializer):
    """Lighter serializer for job lists."""
    
    site_config_name = serializers.CharField(source="site_config.name", read_only=True)
    
    class Meta:
        model = CrawlJob
        fields = [
            "id",
            "site_config_name",
            "status",
            "scheduled_at",
            "finished_at",
            "stats",
        ]


class CrawlLogSerializer(serializers.ModelSerializer):
    """Crawl log serializer."""
    
    class Meta:
        model = CrawlLog
        fields = [
            "id",
            "url",
            "http_status",
            "content_type",
            "fetched_at",
            "duration_ms",
            "leads_found",
            "links_discovered",
            "error",
            "retry_count",
        ]


class TriggerCrawlSerializer(serializers.Serializer):
    """Serializer for triggering a crawl."""
    
    site_config_id = serializers.IntegerField()
    
    def validate_site_config_id(self, value):
        if not SiteConfig.objects.filter(id=value, enabled=True).exists():
            raise serializers.ValidationError("Site config not found or disabled")
        return value