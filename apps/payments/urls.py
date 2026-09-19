from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet, WithdrawalRequestViewSet

router = DefaultRouter()
router.register('withdrawals', WithdrawalRequestViewSet, basename='withdrawal')
router.register('', PaymentViewSet, basename='payment')

urlpatterns = [path('', include(router.urls))]

