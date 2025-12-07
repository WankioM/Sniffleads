from django.db import models
from django.contrib.postgres.fields import ArrayField
from apps.common.models import TimestampedModel


class Lead(TimestampedModel):
    """A potential lead discovered from crawling various sources."""
    
    # Core identity
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255, blank=True, default="")
    company = models.CharField(max_length=255, blank=True, default="")
    
    # Source tracking
    profile_url = models.URLField(max_length=2048)
    source_domain = models.CharField(max_length=255, db_index=True)  # e.g., "medium.com", "linkedin.com"
    
    # Contact info
    email = models.EmailField(blank=True, default="")
    
    # Categorization
    tags = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Tags for categorizing leads (e.g., 'music-production', 'audio-engineering')"
    )
    
    # Raw scraped data for debugging/reprocessing
    raw_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["profile_url", "source_domain"],
                name="unique_lead_per_source"
            )
        ]
        indexes = [
            models.Index(fields=["source_domain", "created_at"]),
            models.Index(fields=["email"]),
        ]
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.name} ({self.source_domain})"