from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from apps.accounts.views import LoginView, SuperAdminDashboardView, ClientDashboardView
from apps.routers.job_views import PendingJobsView, CompleteJobView
from apps.vouchers.views import VoucherScheduleView
from apps.routers.mikrotik_views import (
    HotspotCookiesView, HotspotHostsView, HotspotServersView, IPBindingsView, RouterStatusView, RouterInterfacesView, RouterIPAddressesView,
    HotspotUsersView, HotspotActiveSessionsView, HotspotUserDeleteView,
    RouterRestartView, BandwidthView, RouterFirewallView,
    HotspotProfilesView, RouterLogsView, RouterDNSView, SchedulerView, WalledGardenIPView, WalledGardenView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('api/auth/login/', LoginView.as_view()),
    path('api/auth/refresh/', TokenRefreshView.as_view()),

    # Dashboards
    path('api/dashboard/superadmin/', SuperAdminDashboardView.as_view()),
    path('api/dashboard/client/', ClientDashboardView.as_view()),

    # Resources
    path('api/clients/', include('apps.clients.urls')),
    path('api/routers/', include('apps.routers.urls')),
    path('api/packages/', include('apps.packages.urls')),
    path('api/payments/', include('apps.payments.urls')),
    path('api/vouchers/', include('apps.vouchers.urls')),
    path('api/devices/', include('apps.devices.urls')),
    path('api/sms/', include('apps.sms.urls')),

    # MikroTik Job Polling (VPN)
    path('api/jobs/pending/', PendingJobsView.as_view()),
    path('api/jobs/complete/', CompleteJobView.as_view()),

    # MikroTik Remote Management (Winbox-like)
    path('api/mikrotik/<int:router_id>/status/', RouterStatusView.as_view()),
    path('api/mikrotik/<int:router_id>/interfaces/', RouterInterfacesView.as_view()),
    path('api/mikrotik/<int:router_id>/ip-addresses/', RouterIPAddressesView.as_view()),
    path('api/mikrotik/<int:router_id>/hotspot/users/', HotspotUsersView.as_view()),
    path('api/mikrotik/<int:router_id>/hotspot/users/delete/', HotspotUserDeleteView.as_view()),
    path('api/mikrotik/<int:router_id>/hotspot/sessions/', HotspotActiveSessionsView.as_view()),
    path('api/mikrotik/<int:router_id>/hotspot/profiles/', HotspotProfilesView.as_view()),
    path('api/mikrotik/<int:router_id>/restart/', RouterRestartView.as_view()),
    path('api/mikrotik/<int:router_id>/bandwidth/', BandwidthView.as_view()),
    path('api/mikrotik/<int:router_id>/firewall/', RouterFirewallView.as_view()),
    path('api/mikrotik/<int:router_id>/logs/', RouterLogsView.as_view()),
    path('api/mikrotik/<int:router_id>/dns/', RouterDNSView.as_view()),
    path('api/mikrotik/<int:router_id>/hotspot/servers/', HotspotServersView.as_view()),
    path('api/mikrotik/<int:router_id>/hotspot/hosts/', HotspotHostsView.as_view()),
    path('api/mikrotik/<int:router_id>/hotspot/ip-bindings/', IPBindingsView.as_view()),
    path('api/mikrotik/<int:router_id>/hotspot/walled-garden/', WalledGardenView.as_view()),
    path('api/mikrotik/<int:router_id>/hotspot/walled-garden-ip/', WalledGardenIPView.as_view()),
    path('api/mikrotik/<int:router_id>/hotspot/cookies/', HotspotCookiesView.as_view()),
    path('api/mikrotik/<int:router_id>/voucher/schedule/', VoucherScheduleView.as_view()),
    path('api/mikrotik/<int:router_id>/scheduler/', SchedulerView.as_view()),
]



