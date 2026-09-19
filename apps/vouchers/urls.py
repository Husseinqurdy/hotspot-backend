from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VoucherViewSet,
    VoucherPrintBatchViewSet,
    DailySalesReportViewSet,
    GenerateVoucherPDFView,
)

router = DefaultRouter()
# MUHIMU: routes maalum lazima zisajiliwe KABLA ya '' (VoucherViewSet),
# vinginevyo DefaultRouter itagongana kwa sababu '' inashika kila kitu.
router.register('print-batches', VoucherPrintBatchViewSet, basename='voucher-print-batch')
router.register('sales-reports', DailySalesReportViewSet, basename='daily-sales-report')
router.register('', VoucherViewSet, basename='voucher')

urlpatterns = [
    # generate-pdf/ ni APIView ya kawaida (siyo ViewSet), lazima iwe KABLA
    # ya router.urls — vinginevyo VoucherViewSet (ReadOnlyModelViewSet)
    # inaishika kama 'retrieve' (pk="generate-pdf") na kukataa POST (405).
    path('generate-pdf/', GenerateVoucherPDFView.as_view()),
    path('', include(router.urls)),
]

