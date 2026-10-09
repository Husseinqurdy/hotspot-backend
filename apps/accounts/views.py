import logging
from django.db.models import Q
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
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'full_name': user.get_full_name()
            }
        }
        if user.is_client():
            try:
                from apps.clients.models import Client
                c = Client.objects.get(user=user)
                data['client'] = {
                    'id': c.id,
                    'business_name': c.business_name,
                    'identifier': c.identifier,  # ✅ reference_prefix → identifier
                    'balance': str(c.balance)
                }
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
                'id': c.id,
                'business_name': c.business_name,
                'identifier': c.identifier,  # ✅ reference_prefix → identifier
                'balance': str(c.balance),
                'commission_rate': str(c.commission_rate),
                'is_active': c.is_active,
                'username': c.user.username,
                'email': c.user.email,
                'phone': c.phone,
                'total_payments': Payment.objects.filter(client=c, status='completed').count(),
                'total_vouchers': Voucher.objects.filter(client=c).count(),
                'total_routers': MikroTikRouter.objects.filter(client=c).count(),
                # MPYA: vifaa vya GSM anavyomiliki client huyu mahususi
                # — inasaidia superadmin kuona haraka client gani bado
                # hana kifaa chake mwenyewe (isolation migration progress).
                'total_gsm_devices': GSMDevice.objects.filter(client=c).count(),
            })

                # ── Ongezeko la Clients na Routers kwa kila mwezi (miezi 6
        # iliyopita, ikijumuisha huu wa sasa) ──
        import calendar
        months_back = 6
        month_keys, month_labels = [], []
        cursor = today.replace(day=1)
        for _ in range(months_back):
            month_keys.append((cursor.year, cursor.month))
            month_labels.append(f"{calendar.month_abbr[cursor.month]} {cursor.year}")
            cursor = (cursor.replace(day=1) - timezone.timedelta(days=1)).replace(day=1)
        month_keys.reverse()
        month_labels.reverse()

        clients_by_month = {mk: 0 for mk in month_keys}
        for c in Client.objects.filter(created_at__year__gte=month_keys[0][0]):
            key = (c.created_at.year, c.created_at.month)
            if key in clients_by_month:
                clients_by_month[key] += 1

        routers_by_month = {mk: 0 for mk in month_keys}
        for r in MikroTikRouter.objects.filter(created_at__year__gte=month_keys[0][0]):
            key = (r.created_at.year, r.created_at.month)
            if key in routers_by_month:
                routers_by_month[key] += 1

        growth_by_month = [
            {'month': month_labels[i], 'clients': clients_by_month[month_keys[i]], 'routers': routers_by_month[month_keys[i]]}
            for i in range(months_back)
        ]

        return Response({
            'stats': {
                'total_clients': Client.objects.count(),
                'active_clients': Client.objects.filter(is_active=True).count(),
                'total_routers': MikroTikRouter.objects.count(),
                'online_routers': MikroTikRouter.objects.filter(is_online=True).count(),
                'today_revenue': str(sum(p.amount for p in today_payments)),
                'today_commission': str(sum(p.commission_amount for p in today_payments)),
                'total_vouchers_today': Voucher.objects.filter(created_at__date=today).count(),
                # HII INABAKI GLOBAL KWA MAKUSUDI: superadmin pekee
                # anaona jumla ya vifaa vya mfumo mzima — si isolation
                # bug, endpoint hii ni ya superadmin, si ya client.
                'growth_by_month': growth_by_month,
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

        # ✅ MAREKEBISHO YA ISOLATION BUG: kabla ilikuwa
        # GSMDevice.objects.filter(is_active=True) — BILA client —
        # hivyo kila client alikuwa akiona lipa namba za clients WOTE
        # kwenye dashboard yake. Sasa imefungwa kwa vifaa anavyomiliki
        # client huyu MWENYEWE, pamoja na vifaa vya wengine
        # alivyoongezwa kwenye shared_with (kwa hiari yao) — Q()
        # inashughulikia hali zote mbili.
        devices = GSMDevice.objects.filter(
            Q(client=client) | Q(shared_with=client), is_active=True
        ).distinct().order_by('network')
        lipa_numbers = [
            {
                'network': d.network,
                'network_display': d.get_network_display(),
                'lipa_number': d.lipa_number
            }
            for d in devices
        ]
        recent = [
            {
                'code': v.code,
                'package': v.package.name,
                'customer_phone': v.customer_phone,
                'status': v.status,
                'created_at': v.created_at
            }
            for v in today_vouchers.select_related('package').order_by('-created_at')[:10]
        ]
        
                # ── Vocha za saa kwa saa (kwa 'Leo' bar chart) — kulingana na
        # USED_AT (zilizoingia kwenye scheduler = zimetumika kweli),
        # SIYO created_at — sawa na jinsi DailySalesReport inavyohesabu.
        used_today = Voucher.objects.filter(
            client=client, used_at__date=today
        ).select_related('package')

        hourly_counts = {h: 0 for h in range(24)}
        for v in used_today:
            hourly_counts[timezone.localtime(v.used_at).hour] += 1
        hourly_vouchers = [
            {'hour': f'{h:02d}:00', 'count': hourly_counts[h]}
            for h in range(24)
        ]

        # ── Mgawanyo kwa Package (kwa 'circle/donut' chart) ──
        package_counts = {}
        for v in used_today:
            name = v.package.name if v.package else 'Nyingine'
            package_counts[name] = package_counts.get(name, 0) + 1
        total_used_today = sum(package_counts.values())
        package_breakdown = [
            {
                'name': name,
                'count': count,
                'percent': round(count / total_used_today * 100, 1) if total_used_today else 0,
            }
            for name, count in sorted(package_counts.items(), key=lambda x: -x[1])
        ]

        return Response({
            'client': {
                'business_name': client.business_name,
                'identifier': client.identifier,  # ✅ reference_prefix → identifier
                'balance': str(client.balance),
                # MPYA: frontend inatumia hii kuamua ni maelekezo gani
                # ya malipo ya kuonyesha — client asiye na sharing
                # yoyote (False) haihitaji tena kuonyesha 'YOUR NUMBER'
                # wala kuomba customer aongeze chochote kwenye bei.
                'requires_payment_identifier': client.requires_payment_identifier(),
            },
            'lipa_numbers': lipa_numbers,
            'hourly_vouchers': hourly_vouchers,
            'package_breakdown': package_breakdown,
            'stats': {
                'total_routers': MikroTikRouter.objects.filter(client=client).count(),
                'online_routers': MikroTikRouter.objects.filter(client=client, is_online=True).count(),
                'total_packages': Package.objects.filter(client=client, is_active=True).count(),
                'today_payments': today_payments.count(),
                'today_vouchers': today_vouchers.count(),
                'today_revenue': str(sum(p.client_share for p in today_payments)),
                'month_revenue': str(sum(p.client_share for p in Payment.objects.filter(
                    client=client, status='completed', created_at__month=today.month
                ))),
            },
            'recent_vouchers': recent,
        })


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        data = {
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'phone': user.phone,
                'role': user.role,
                'full_name': user.get_full_name()
            }
        }
        if user.is_client():
            try:
                from apps.clients.models import Client
                c = Client.objects.get(user=user)
                data['client'] = {
                    'id': c.id,
                    'business_name': c.business_name,
                    'identifier': c.identifier,
                    'balance': str(c.balance)
                }
            except Exception:
                pass
        return Response(data)

    def patch(self, request):
        # Ruhusu kubadilisha phone tu — hakuna anayeweza kujibadilishia
        # username, email au role kupitia endpoint hii
        user = request.user
        if 'phone' in request.data:
            user.phone = request.data.get('phone', '')
            user.save(update_fields=['phone'])
        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'phone': user.phone,
                'role': user.role,
                'full_name': user.get_full_name()
            }
        })


class ChangeOwnPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get('old_password', '')
        new_password = request.data.get('new_password', '')

        if not old_password or not new_password:
            return Response({'error': 'Password ya zamani na mpya zinahitajika'}, status=400)
        if len(new_password) < 6:
            return Response({'error': 'Password mpya lazima iwe na herufi angalau 6'}, status=400)

        user = request.user
        if not user.check_password(old_password):
            return Response({'error': 'Password ya zamani si sahihi'}, status=400)

        user.set_password(new_password)
        user.save(update_fields=['password'])
        return Response({'message': 'Password imebadilishwa kikamilifu'})
