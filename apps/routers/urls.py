from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RouterViewSet
router = DefaultRouter()
router.register('', RouterViewSet, basename='router')
urlpatterns = [path('', include(router.urls))]