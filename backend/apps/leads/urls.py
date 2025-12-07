# apps/leads/urls.py

from rest_framework.routers import DefaultRouter
from .views import LeadViewSet

router = DefaultRouter()
router.register(r"leads", LeadViewSet, basename="lead")

urlpatterns = router.urls