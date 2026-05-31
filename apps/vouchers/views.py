from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Voucher
from .serializers import VoucherSerializer
from rest_framework.views import APIView


class VoucherViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VoucherSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        qs = Voucher.objects.select_related('client','router','package').all() if self.request.user.is_superadmin() else Voucher.objects.filter(client__user=self.request.user).select_related('client','router','package')
        for f,k in [('status','status'),('client','client_id'),('date_from','created_at__date__gte'),('date_to','created_at__date__lte')]:
            if v := self.request.query_params.get(f): qs = qs.filter(**{k:v})
        return qs
    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.get_queryset()
        return Response({'total':qs.count(),'active':qs.filter(status='active').count(),'used':qs.filter(status='used').count(),'expired':qs.filter(status='expired').count()})
    
    
# ── Ongeza kwenye apps/vouchers/views.py ─────────────────────────────────────
# Hii inaendelea baada ya VoucherViewSet



class VoucherScheduleView(APIView):
    """
    Inapoitwa wakati mtumiaji anaingiza voucher — inaunda scheduler kwenye MikroTik
    ili voucher iondolewe automatically baada ya muda wake kwisha.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, router_id):
        """
        Tumia hii baada ya mtumiaji kuingiza voucher.
        Body: { "username": "ABCD1234", "session_timeout": "2h", "profile": "pkg-500" }
        """
        from apps.routers.models import MikroTikRouter
        from apps.routers.mikrotik import get_mikrotik_connection

        username = request.data.get('username', '')
        session_timeout = request.data.get('session_timeout', '1h')
        profile = request.data.get('profile', '')

        if not username:
            return Response({'error': 'username inahitajika'}, status=400)

        try:
            if request.user.is_superadmin():
                router = MikroTikRouter.objects.get(id=router_id)
            else:
                router = MikroTikRouter.objects.get(id=router_id, client__user=request.user)
        except MikroTikRouter.DoesNotExist:
            return Response({'error': 'Router haikupatikana'}, status=404)

        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)

        try:
            import datetime
            now = datetime.datetime.now()
            # MikroTik scheduler time format: HH:MM:SS
            start_time = now.strftime('%H:%M:%S')
            sched_name = f"vc-{username}"

            # Script: inapoisha muda, futa user na scheduler yenyewe
            on_event = (
                f"/ip/hotspot/user remove [find name=\"{username}\"];"
                f"/system/scheduler remove [find name=\"{sched_name}\"];"
            )

            # Angalia kama scheduler ipo tayari
            existing = api.command('/system/scheduler/print', queries={'name': sched_name})
            if existing:
                # Sasisha
                api.command('/system/scheduler/set', {
                    '.id': existing[0]['.id'],
                    'start-time': start_time,
                    'interval': session_timeout,
                    'on-event': on_event,
                })
            else:
                # Unda mpya
                api.command('/system/scheduler/add', {
                    'name': sched_name,
                    'start-time': start_time,
                    'interval': session_timeout,
                    'on-event': on_event,
                    'comment': f'Voucher expire: {username} | {profile}',
                    'policy': 'read,write,policy,test',
                })

            return Response({
                'message': f'Scheduler imeundwa kwa {username} — itaisha baada ya {session_timeout}',
                'scheduler_name': sched_name,
            })

        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()