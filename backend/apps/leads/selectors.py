from datetime import datetime
from typing import Optional
from django.db import models
from django.db.models import QuerySet, Q
from apps.leads.models import Lead


def get_lead_by_id(lead_id: int) -> Optional[Lead]:
    """Get a single lead by ID."""
    try:
        return Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return None


def get_leads_by_source(source_domain: str) -> QuerySet[Lead]:
    """Get all leads from a specific source."""
    return Lead.objects.filter(source_domain=source_domain)


def get_leads_by_tag(tag: str) -> QuerySet[Lead]:
    """Get all leads with a specific tag."""
    return Lead.objects.filter(tags__contains=[tag])


def get_leads_with_email() -> QuerySet[Lead]:
    """Get all leads that have an email address."""
    return Lead.objects.exclude(email="")


def search_leads(
    query: Optional[str] = None,
    source_domain: Optional[str] = None,
    tags: Optional[list[str]] = None,
    has_email: Optional[bool] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
) -> QuerySet[Lead]:
    """
    Search leads with multiple filters.
    
    Args:
        query: Search in name, role, company
        source_domain: Filter by source
        tags: Filter by any of these tags
        has_email: True = has email, False = no email
        created_after: Filter by creation date
        created_before: Filter by creation date
    """
    qs = Lead.objects.all()
    
    if query:
        qs = qs.filter(
            Q(name__icontains=query) |
            Q(role__icontains=query) |
            Q(company__icontains=query)
        )
    
    if source_domain:
        qs = qs.filter(source_domain=source_domain)
    
    if tags:
        # Match any of the provided tags
        qs = qs.filter(tags__overlap=tags)
    
    if has_email is True:
        qs = qs.exclude(email="")
    elif has_email is False:
        qs = qs.filter(email="")
    
    if created_after:
        qs = qs.filter(created_at__gte=created_after)
    
    if created_before:
        qs = qs.filter(created_at__lte=created_before)
    
    return qs


def get_lead_stats() -> dict:
    """Get summary statistics about leads."""
    total = Lead.objects.count()
    with_email = Lead.objects.exclude(email="").count()
    by_source = (
        Lead.objects
        .values("source_domain")
        .annotate(count=models.Count("id"))
        .order_by("-count")
    )
    
    return {
        "total": total,
        "with_email": with_email,
        "by_source": list(by_source),
    }