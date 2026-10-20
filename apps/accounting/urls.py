from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SiteViewSet, EntryViewSet, SummaryView, LogView, AccessView, ExportView

router = DefaultRouter()
router.register('sites', SiteViewSet, basename='acct-site')
router.register('entries', EntryViewSet, basename='acct-entry')

urlpatterns = [
    path('summary/', SummaryView.as_view()),
    path('logs/', LogView.as_view()),
    path('access/', AccessView.as_view()),
    path('export/', ExportView.as_view()),
    path('', include(router.urls)),
]
