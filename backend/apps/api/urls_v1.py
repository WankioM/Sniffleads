# apps/api/urls_v1.py

from django.urls import path, include

urlpatterns = [
    path("", include("apps.leads.urls")),
    path("sources/", include("apps.sources.urls")),
]