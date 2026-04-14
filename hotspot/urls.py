from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from apps.accounts.views import LoginView, SuperAdminDashboardView, ClientDashboardView
from apps.routers.job_views import PendingJobsView, CompleteJobView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/login/', LoginView.as_view()),
    path('api/auth/refresh/', TokenRefreshView.as_view()),
    path('api/dashboard/superadmin/', SuperAdminDashboardView.as_view()),
    path('api/dashboard/client/', ClientDashboardView.as_view()),
    path('api/clients/', include('apps.clients.urls')),
    path('api/routers/', include('apps.routers.urls')),
    path('api/packages/', include('apps.packages.urls')),
    path('api/payments/', include('apps.payments.urls')),
    path('api/vouchers/', include('apps.vouchers.urls')),
    path('api/devices/', include('apps.devices.urls')),
    path('api/sms/', include('apps.sms.urls')),
    path('api/jobs/pending/', PendingJobsView.as_view()),
    path('api/jobs/complete/', CompleteJobView.as_view()),
]
