from django.urls import path, include

urlpatterns = [
    path("leads/", include("apps.leads.urls")),
    path("sources/", include("apps.sources.urls")),
    path("accounts/", include("apps.accounts.urls")),
]