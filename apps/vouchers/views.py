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


class VoucherPrintBatchViewSet(viewsets.ModelViewSet):
    """
    Historia ya PDF za vocha (Sehemu ya 1 ya Analysis page).
    GET (list/retrieve) na DELETE tu — hatuunda/kuhariri kupitia viewset hii,
    kuundwa kunafanyika na GenerateVoucherPDFView.
    """
    http_method_names = ['get', 'delete']
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from .serializers import VoucherPrintBatchSerializer
        return VoucherPrintBatchSerializer

    def get_queryset(self):
        from .models import VoucherPrintBatch
        if self.request.user.is_superadmin():
            return VoucherPrintBatch.objects.select_related('client', 'router', 'package').all()
        return VoucherPrintBatch.objects.filter(
            client__user=self.request.user
        ).select_related('client', 'router', 'package')

    def destroy(self, request, *args, **kwargs):
        batch = self.get_object()
        if batch.pdf_file:
            batch.pdf_file.delete(save=False)
        batch.delete()
        return Response(status=204)


class GenerateVoucherPDFView(APIView):
    """
    Inaitwa na frontend MARA MOJA baada ya kumaliza loop ya kuunda vouchers
    (single au batch) — inatengeneza PDF moja ya kundi zima na kuihifadhi
    kama VoucherPrintBatch.

    Body: { "codes": ["ABCD1234", ...], "theme": "blue" }
    (kwa super admin pekee: ongeza pia "client_id")
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.core.files.base import ContentFile
        from apps.clients.models import Client
        from .models import Voucher, VoucherPrintBatch
        from .pdf import build_voucher_pdf

        codes = request.data.get('codes', [])
        theme = request.data.get('theme', 'blue')

        if not codes:
            return Response({'error': 'codes inahitajika'}, status=400)

        if request.user.is_superadmin():
            client_id = request.data.get('client_id')
            if not client_id:
                return Response({'error': 'client_id inahitajika kwa admin'}, status=400)
            try:
                client_obj = Client.objects.get(id=client_id)
            except Client.DoesNotExist:
                return Response({'error': 'Client haikupatikana'}, status=404)
            vouchers_qs = Voucher.objects.filter(code__in=codes, client=client_obj)
        else:
            vouchers_qs = Voucher.objects.filter(code__in=codes, client__user=request.user)

        vouchers = list(vouchers_qs.select_related('package', 'router', 'client'))
        if not vouchers:
            return Response({'error': 'Hakuna vouchers zilizopatikana kwa codes hizo'}, status=404)

        client = vouchers[0].client
        router = vouchers[0].router
        package = vouchers[0].package
        business_name = client.business_name

        voucher_data = []
        for v in vouchers:
            pkg = v.package
            voucher_data.append({
                'code': v.code,
                'package_name': pkg.name if pkg else '—',
                'price': float(v.sold_price),
                'duration': pkg.duration_display() if pkg else '—',
                'speed': f"{pkg.speed_down}mb / {pkg.speed_up}mb" if pkg else '—',
            })

        try:
            pdf_bytes = build_voucher_pdf(business_name, theme, voucher_data)
        except Exception as e:
            import logging
            logging.getLogger('netsafi').error(f"GenerateVoucherPDFView PDF error: {e}")
            return Response({'error': f'PDF generation imeshindwa: {e}'}, status=500)

        batch = VoucherPrintBatch.objects.create(
            client=client,
            router=router,
            package=package,
            profile_name=package.mikrotik_profile if package else '',
            unit_price=package.price if package else 0,
            quantity=len(vouchers),
            theme=theme,
            created_by=request.user,
        )
        filename = f"vouchers_{batch.profile_name}_{batch.id}.pdf"
        batch.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)

        Voucher.objects.filter(code__in=codes).update(print_batch=batch)

        from .serializers import VoucherPrintBatchSerializer
        return Response(
            VoucherPrintBatchSerializer(batch, context={'request': request}).data,
            status=201,
        )


class DailySalesReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Ripoti za mauzo za kila siku (Sehemu ya 2 ya Analysis page).
    Query param ya hiari: ?days=30 (default: zote).
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from .serializers import DailySalesReportSerializer
        return DailySalesReportSerializer

    def get_queryset(self):
        from .models import DailySalesReport
        if self.request.user.is_superadmin():
            qs = DailySalesReport.objects.select_related('client').all()
        else:
            qs = DailySalesReport.objects.filter(client__user=self.request.user)

        days = self.request.query_params.get('days')
        if days:
            try:
                from django.utils import timezone
                from datetime import timedelta
                cutoff = timezone.localdate() - timedelta(days=int(days))
                qs = qs.filter(date__gte=cutoff)
            except ValueError:
                pass
        return qs

