# apps/leads/views.py

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Lead
from .serializers import LeadSerializer, LeadListSerializer, LeadCreateSerializer
from .selectors import get_lead_stats


class LeadViewSet(viewsets.ModelViewSet):
    """
    API endpoints for leads.
    
    list:       GET    /api/v1/leads/
    create:     POST   /api/v1/leads/
    retrieve:   GET    /api/v1/leads/{id}/
    update:     PUT    /api/v1/leads/{id}/
    partial:    PATCH  /api/v1/leads/{id}/
    destroy:    DELETE /api/v1/leads/{id}/
    stats:      GET    /api/v1/leads/stats/
    """
    
    queryset = Lead.objects.all().order_by("-created_at")
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    
    # Search across text fields
    search_fields = ["name", "role", "company", "email"]
    
    # Allow ordering by these fields
    ordering_fields = ["created_at", "updated_at", "name", "company"]
    ordering = ["-created_at"]
    
    def get_serializer_class(self):
        if self.action == "list":
            return LeadListSerializer
        if self.action == "create":
            return LeadCreateSerializer
        return LeadSerializer
    
    def get_queryset(self):
        """Apply additional filters from query params."""
        queryset = super().get_queryset()
        
        # Filter by source_domain
        source = self.request.query_params.get("source_domain")
        if source:
            queryset = queryset.filter(source_domain=source)
        
        # Filter by tag (tags is ArrayField)
        tag = self.request.query_params.get("tag")
        if tag:
            queryset = queryset.filter(tags__contains=[tag])
        
        # Filter by date range
        created_after = self.request.query_params.get("created_after")
        if created_after:
            queryset = queryset.filter(created_at__gte=created_after)
        
        created_before = self.request.query_params.get("created_before")
        if created_before:
            queryset = queryset.filter(created_at__lte=created_before)
        
        return queryset
    
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get lead statistics."""
        stats = get_lead_stats()
        return Response(stats)