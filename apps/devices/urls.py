from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GSMDeviceViewSet
router = DefaultRouter()
router.register('', GSMDeviceViewSet, basename='device')
urlpatterns = [path('', include(router.urls))]