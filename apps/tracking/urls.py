from django.urls import path
from .views import VoucherLookupView, VoucherLiveView

urlpatterns = [
    path('voucher/', VoucherLookupView.as_view()),
    path('voucher/live/', VoucherLiveView.as_view()),
]
