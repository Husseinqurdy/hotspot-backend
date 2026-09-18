from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'advertisers', views.AdvertiserViewSet, basename='advertiser')
router.register(r'advertisements', views.AdvertisementViewSet, basename='advertisement')

urlpatterns = [
    path('', include(router.urls)),

    # Public - zinaitwa na captive portal (login.html)
    path('active/', views.active_ad, name='ads-active'),
    path('impression/', views.record_impression, name='ads-impression'),
    path('click/', views.record_click, name='ads-click'),
    path('grant-sponsored/', views.grant_sponsored_access, name='ads-grant-sponsored'),

    # Dashboard reporting
    path('report/', views.ad_report, name='ads-report'),
]

