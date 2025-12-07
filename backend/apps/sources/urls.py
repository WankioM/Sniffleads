# apps/sources/urls.py

from rest_framework.routers import DefaultRouter
from .views import SiteConfigViewSet, CrawlJobViewSet

router = DefaultRouter()
router.register(r"configs", SiteConfigViewSet, basename="siteconfig")
router.register(r"jobs", CrawlJobViewSet, basename="crawljob")

urlpatterns = router.urls