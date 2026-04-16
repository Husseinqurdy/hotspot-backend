import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from django.contrib.auth.hashers import make_password

logger = logging.getLogger('netsafi')


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')
        if not username or not password:
            return Response({'error': 'Username na password zinahitajika'}, status=400)
        user = authenticate(username=username, password=password)
        if not user:
            return Response({'error': 'Username au password si sahihi'}, status=401)
        if not user.is_active:
            return Response({'error': 'Akaunti yako imezuiwa. Wasiliana na msimamizi.'}, status=403)
        refresh = RefreshToken.for_user(user)
        data = {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {'id': user.id, 'username': user.username, 'email': user.email, 'role': user.role, 'full_name': user.get_full_name()}
        }
        if user.is_client():
            try:
                from apps.clients.models import Client
                c = Client.objects.get(user=user)
                data['client'] = {'id': c.id, 'business_name': c.business_name, 'reference_prefix': c.reference_prefix, 'balance': str(c.balance)}
            except Exception:
                pass
        return Response(data)


class SuperAdminDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superadmin():
            return Response(status=403)
        from apps.clients.models import Client
        from apps.routers.models import MikroTikRouter, MikroTikJob
        from apps.payments.models import Payment
        from apps.vouchers.models import Voucher
        from apps.devices.models import GSMDevice

        today = timezone.now().date()
        today_payments = Payment.objects.filter(status='completed', created_at__date=today)

        clients_data = []
        for c in Client.objects.select_related('user').all():
            clients_data.append({
                'id': c.id, 'business_name': c.business_name,
                'reference_prefix': c.reference_prefix, 'balance': str(c.balance),
                'commission_rate': str(c.commission_rate),
                'is_active': c.is_active,
                'username': c.user.username,
                'email': c.user.email,
                'phone': c.phone,
                'total_payments': Payment.objects.filter(client=c, status='completed').count(),
                'total_vouchers': Voucher.objects.filter(client=c).count(),
                'total_routers': MikroTikRouter.objects.filter(client=c).count(),
            })

        return Response({
            'stats': {
                'total_clients': Client.objects.count(),
                'active_clients': Client.objects.filter(is_active=True).count(),
                'total_routers': MikroTikRouter.objects.count(),
                'online_routers': MikroTikRouter.objects.filter(is_online=True).count(),
                'today_revenue': str(sum(p.amount for p in today_payments)),
                'today_commission': str(sum(p.commission_amount for p in today_payments)),
                'total_vouchers_today': Voucher.objects.filter(created_at__date=today).count(),
                'total_devices': GSMDevice.objects.count(),
                'active_devices': GSMDevice.objects.filter(is_active=True).count(),
                'pending_jobs': MikroTikJob.objects.filter(status='pending').count(),
            },
            'clients': clients_data,
        })


class ClientDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_client():
            return Response(status=403)
        from apps.clients.models import Client
        from apps.routers.models import MikroTikRouter
        from apps.packages.models import Package
        from apps.payments.models import Payment
        from apps.vouchers.models import Voucher
        from apps.devices.models import GSMDevice

        client = Client.objects.get(user=request.user)
        today = timezone.now().date()
        today_payments = Payment.objects.filter(client=client, status='completed', created_at__date=today)
        today_vouchers = Voucher.objects.filter(client=client, created_at__date=today)
        devices = GSMDevice.objects.filter(is_active=True).order_by('network')
        lipa_numbers = [{'network': d.network, 'network_display': d.get_network_display(), 'lipa_number': d.lipa_number} for d in devices]
        recent = [{'code': v.code, 'package': v.package.name, 'customer_phone': v.customer_phone, 'status': v.status, 'created_at': v.created_at} for v in today_vouchers.select_related('package').order_by('-created_at')[:10]]

        return Response({
            'client': {'business_name': client.business_name, 'reference_prefix': client.reference_prefix, 'balance': str(client.balance)},
            'lipa_numbers': lipa_numbers,
            'stats': {
                'total_routers': MikroTikRouter.objects.filter(client=client).count(),
                'online_routers': MikroTikRouter.objects.filter(client=client, is_online=True).count(),
                'total_packages': Package.objects.filter(client=client, is_active=True).count(),
                'today_payments': today_payments.count(),
                'today_vouchers': today_vouchers.count(),
                'today_revenue': str(sum(p.client_share for p in today_payments)),
                'month_revenue': str(sum(p.client_share for p in Payment.objects.filter(client=client, status='completed', created_at__month=today.month))),
            },
            'recent_vouchers': recent,
        })
