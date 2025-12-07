# apps/leads/serializers.py

from rest_framework import serializers
from .models import Lead


class LeadSerializer(serializers.ModelSerializer):
    """Full lead serializer with all fields."""
    
    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "role",
            "company",
            "profile_url",
            "source_domain",
            "email",
            "tags",
            "raw_data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class LeadListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views."""
    
    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "role",
            "company",
            "profile_url",
            "source_domain",
            "tags",
            "created_at",
        ]


class LeadCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating leads manually."""
    
    class Meta:
        model = Lead
        fields = [
            "name",
            "role",
            "company",
            "profile_url",
            "source_domain",
            "email",
            "tags",
            "raw_data",
        ]
    
    def validate_profile_url(self, value):
        """Ensure profile_url is a valid URL."""
        if not value.startswith(("http://", "https://")):
            raise serializers.ValidationError("Must be a valid URL")
        return value