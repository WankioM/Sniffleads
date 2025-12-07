from typing import Optional
from apps.leads.models import Lead


def upsert_lead(
    profile_url: str,
    source_domain: str,
    name: str,
    role: str = "",
    company: str = "",
    email: str = "",
    tags: Optional[list[str]] = None,
    raw_data: Optional[dict] = None,
) -> tuple[Lead, bool]:
    """
    Create or update a lead based on profile_url + source_domain.
    
    Returns:
        tuple: (lead_instance, created) where created is True if new lead
    """
    tags = tags or []
    raw_data = raw_data or {}
    
    lead, created = Lead.objects.update_or_create(
        profile_url=profile_url,
        source_domain=source_domain,
        defaults={
            "name": name,
            "role": role,
            "company": company,
            "email": email,
            "tags": tags,
            "raw_data": raw_data,
        }
    )
    
    return lead, created