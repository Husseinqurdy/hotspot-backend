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

    Query params (zote hiari, zinaweza kuchanganywa):
      ?days=30                        — siku N zilizopita kutoka leo
      ?start=2026-08-01&end=2026-09-30 — range maalum (custom range, siku
                                          zozote — mwezi, siku 60, n.k.)
      ?client=5                        — (superadmin pekee) client mahususi

    MUHIMU: pagination_class = None — bila hii, DRF ilikuwa ikirudisha
    ukurasa wa KWANZA TU (PAGE_SIZE=20 settings.py), ikikata ripoti
    yoyote ya zaidi ya siku 20 bila kujali 'days'/'start'/'end'
    iliyoombwa. Ripoti hizi ni ndogo sana kwa asili (rekodi MOJA kwa
    kila siku kwa kila client) — hata miaka kadhaa ya data haiwezi
    kuzidi mamia machache ya rekodi, hivyo kuzima pagination ni salama
    kabisa hapa.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_serializer_class(self):
        from .serializers import DailySalesReportSerializer
        return DailySalesReportSerializer

    def get_queryset(self):
        from .models import DailySalesReport
        if self.request.user.is_superadmin():
            qs = DailySalesReport.objects.select_related('client').all()
            client_id = self.request.query_params.get('client')
            if client_id:
                qs = qs.filter(client_id=client_id)
        else:
            qs = DailySalesReport.objects.filter(client__user=self.request.user)

        qs = self._apply_date_filters(qs)
        return qs

    def _apply_date_filters(self, qs):
        """
        Inatumika na get_queryset() NA export_pdf() — 'start'/'end'
        (custom range) vina kipaumbele juu ya 'days' (preset) endapo
        vyote vimetolewa kwa pamoja.
        """
        from django.utils import timezone
        from datetime import timedelta, date as date_cls

        start = self.request.query_params.get('start')
        end = self.request.query_params.get('end')
        if start:
            try:
                qs = qs.filter(date__gte=date_cls.fromisoformat(start))
            except ValueError:
                pass
        if end:
            try:
                qs = qs.filter(date__lte=date_cls.fromisoformat(end))
            except ValueError:
                pass

        if not start and not end:
            days = self.request.query_params.get('days')
            if days:
                try:
                    cutoff = timezone.localdate() - timedelta(days=int(days))
                    qs = qs.filter(date__gte=cutoff)
                except ValueError:
                    pass
        return qs

    @action(detail=False, methods=['get'], url_path='export-pdf')
    def export_pdf(self, request):
        """
        Pakua PDF ya ripoti ya mauzo kwa range iliyochaguliwa — inatumia
        query params zile zile za get_queryset() (?days= au ?start=&end=,
        na ?client= kwa superadmin).
        """
        from django.http import HttpResponse
        from weasyprint import HTML
        from django.utils import timezone

        qs = self.get_queryset().order_by('date')
        reports = list(qs)

        if not reports:
            return Response({'error': 'Hakuna data kwa muda uliochagua'}, status=404)

        start_param = request.query_params.get('start')
        end_param = request.query_params.get('end')
        if start_param and end_param:
            range_label = f"{start_param} hadi {end_param}"
        else:
            range_label = f"Siku {len(reports)} za mwisho (tarehe {reports[0].date} hadi {reports[-1].date})"

        multi_client = request.user.is_superadmin() and not request.query_params.get('client')
        business_name = 'Clients Wote' if multi_client else reports[0].client.business_name

        total_vouchers = sum(r.total_vouchers_sold for r in reports)
        total_revenue = sum(r.total_revenue for r in reports)

        # Kama ni multi-client (superadmin, bila client filter), unganisha
        # kwa tarehe moja (jumla ya clients wote siku hiyo) ili jedwali
        # lisome vizuri — vinginevyo (client mmoja) ni safi tayari.
        if multi_client:
            merged = {}
            for r in reports:
                merged.setdefault(r.date, {'vouchers': 0, 'revenue': 0})
                merged[r.date]['vouchers'] += r.total_vouchers_sold
                merged[r.date]['revenue'] += r.total_revenue
            rows = [
                {'date': d, 'vouchers': v['vouchers'], 'revenue': v['revenue']}
                for d, v in sorted(merged.items())
            ]
        else:
            rows = [
                {'date': r.date, 'vouchers': r.total_vouchers_sold, 'revenue': r.total_revenue}
                for r in reports
            ]

        rows_html = ''.join(
            f"<tr><td>{r['date'].strftime('%d/%m/%Y')}</td>"
            f"<td style='text-align:center'>{r['vouchers']}</td>"
            f"<td style='text-align:right'>{r['revenue']:,.0f}</td></tr>"
            for r in rows
        )

        html = f"""
        <html>
        <head>
        <style>
            @page {{ size: A4; margin: 18mm 15mm; }}
            body {{ font-family: Helvetica, Arial, sans-serif; color: #1c2833; font-size: 12px; }}
            h1 {{ font-size: 20px; color: #154360; margin-bottom: 2px; }}
            .meta {{ color: #5d6d7e; font-size: 12px; margin-bottom: 18px; }}
            .summary {{ display: flex; gap: 20px; margin-bottom: 20px; }}
            .box {{ background: #eaf2f8; border-radius: 8px; padding: 12px 18px; }}
            .box .label {{ font-size: 10px; color: #5d6d7e; text-transform: uppercase; }}
            .box .value {{ font-size: 20px; font-weight: 700; color: #154360; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th {{ background: #154360; color: #fff; text-align: left; padding: 8px 10px; font-size: 11px; }}
            td {{ border-bottom: 1px solid #d5dbdb; padding: 6px 10px; font-size: 11px; }}
            tr:nth-child(even) td {{ background: #f8f9f9; }}
            .footer {{ margin-top: 30px; font-size: 9px; color: #95a5a6; text-align: center; }}
        </style>
        </head>
        <body>
            <h1>Ripoti ya Mauzo — {business_name}</h1>
            <p class="meta">Kipindi: {range_label} &nbsp;|&nbsp; Imetengenezwa: {timezone.localtime().strftime('%d/%m/%Y %H:%M')}</p>
            <div class="summary">
                <div class="box"><div class="label">Jumla ya Vouchers</div><div class="value">{total_vouchers}</div></div>
                <div class="box"><div class="label">Jumla ya Mapato</div><div class="value">TZS {total_revenue:,.0f}</div></div>
                <div class="box"><div class="label">Wastani/Siku</div><div class="value">TZS {(total_revenue / len(rows) if rows else 0):,.0f}</div></div>
            </div>
            <table>
                <thead><tr><th>Tarehe</th><th style="text-align:center">Vouchers</th><th style="text-align:right">Mapato (TZS)</th></tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
            <p class="footer">NetSafi Hotspot Management — Ripoti hii imetengenezwa kiotomatiki</p>
        </body>
        </html>
        """

        pdf_bytes = HTML(string=html).write_pdf()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"ripoti_mauzo_{reports[0].date}_{reports[-1].date}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

