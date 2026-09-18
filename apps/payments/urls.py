from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet, WithdrawalRequestViewSet

router = DefaultRouter()
router.register('withdrawals', WithdrawalRequestViewSet, basename='withdrawal')
router.register('', PaymentViewSet, basename='payment')
<<<<<<< HEAD

urlpatterns = [path('', include(router.urls))]

=======
urlpatterns = [path('', include(router.urls))]
>>>>>>> ce77eb29d3fbe067206773bcdacb85bba7fb4c3c
