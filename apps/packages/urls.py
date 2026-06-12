from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PackageViewSet, SyncPackageFromMikroTikView, SyncAllPackagesFromMikroTikView

router = DefaultRouter()
router.register('', PackageViewSet, basename='package')

urlpatterns = [
    path('sync-all-from-mikrotik/',              SyncAllPackagesFromMikroTikView.as_view()),
    path('<int:package_id>/sync-from-mikrotik/', SyncPackageFromMikroTikView.as_view()),
    path('', include(router.urls)),
]