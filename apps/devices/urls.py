from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GSMDeviceViewSet, CheckinView

router = DefaultRouter()
router.register('', GSMDeviceViewSet, basename='device')

urlpatterns = [
    # MUHIMU: checkin/ iko NJE ya router (ni APIView ya kawaida ya
    # PUBLIC, siyo sehemu ya ModelViewSet ya GSMDevice). Lazima iwe
    # KABLA ya include(router.urls) ili isije ikagongana na
    # '<pk>/' pattern ya router (ambayo ingejaribu kutafsiri
    # 'checkin' kama pk).
    path('checkin/', CheckinView.as_view(), name='device-checkin'),
    path('', include(router.urls)),
]
