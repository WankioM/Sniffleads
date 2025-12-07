# apps/sources/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import SiteConfig, CrawlJob, CrawlLog
from .serializers import (
    SiteConfigSerializer, SiteConfigListSerializer,
    CrawlJobSerializer, CrawlJobListSerializer, CrawlLogSerializer,
)
from .selectors import get_crawl_stats_summary, get_config_performance
from apps.crawler.tasks import trigger_crawl_for_config


class SiteConfigViewSet(viewsets.ModelViewSet):
    queryset = SiteConfig.objects.all().order_by("domain", "name")
    
    def get_serializer_class(self):
        if self.action == "list":
            return SiteConfigListSerializer
        return SiteConfigSerializer
    
    @action(detail=True, methods=["post"])
    def crawl(self, request, pk=None):
        config = self.get_object()
        if not config.enabled:
            return Response({"error": "Site config is disabled"}, status=status.HTTP_400_BAD_REQUEST)
        result = trigger_crawl_for_config.delay(site_config_id=config.id, triggered_by="api")
        return Response({"message": "Crawl triggered", "task_id": result.id, "site_config": config.name})
    
    @action(detail=True, methods=["get"])
    def performance(self, request, pk=None):
        config = self.get_object()
        days = int(request.query_params.get("days", 7))
        return Response(get_config_performance(config, days=days))


class CrawlJobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CrawlJob.objects.select_related("site_config").order_by("-scheduled_at")
    
    def get_serializer_class(self):
        if self.action == "list":
            return CrawlJobListSerializer
        return CrawlJobSerializer
    
    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        job = self.get_object()
        logs = job.logs.all().order_by("-fetched_at")[:100]
        return Response(CrawlLogSerializer(logs, many=True).data)
    
    @action(detail=False, methods=["get"])
    def stats(self, request):
        return Response(get_crawl_stats_summary())