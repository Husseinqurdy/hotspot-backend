import logging
from django.db.models import Sum, Count, F
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Payment, WithdrawalRequest
from .serializers import PaymentSerializer, WithdrawalRequestSerializer

logger = logging.getLogger('netsafi')


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        if self.request.user.is_superuser:
            qs = Payment.objects.select_related(
                'client',
                'package',
                'client_package_price'
            ).all()

        else:
            qs = Payment.objects.select_related(
                'client',
                'package',
                'client_package_price'
            ).filter(
                client__user=self.request.user
            )

        # FILTERS
        filters = [
            ('status', 'status'),
            ('network', 'network'),
            ('date_from', 'created_at__date__gte'),
            ('date_to', 'created_at__date__lte'),
        ]

        for param, field in filters:

            value = self.request.query_params.get(param)

            if value:
                qs = qs.filter(**{field: value})

        return qs

    @action(detail=False, methods=['get'])
    def summary(self, request):

        qs = self.get_queryset().filter(
            status=Payment.STATUS_COMPLETED
        )

        totals = qs.aggregate(
            total_amount=Sum('amount'),
            total_commission=Sum('commission_amount'),
            total_client_share=Sum('client_share'),
            total_payments=Count('id')
        )

        # BY NETWORK
        by_network = {}

        network_data = (
            qs.values('network')
            .annotate(total=Sum('amount'))
        )

        for item in network_data:
            by_network[item['network']] = item['total']

        # BY PACKAGE
        by_package = {}

        package_data = (
            qs.values('package__name')
            .annotate(total=Sum('amount'))
        )

        for item in package_data:
            package_name = item['package__name'] or 'Unknown'
            by_package[package_name] = item['total']

        return Response({
            'total_payments': totals['total_payments'] or 0,
            'total_amount': totals['total_amount'] or 0,
            'total_commission': totals['total_commission'] or 0,
            'total_client_share': totals['total_client_share'] or 0,
            'by_network': by_network,
            'by_package': by_package,
        })


# ══════════════════════════════════════════════════════════════
# WITHDRAWALS: Client anaomba kutoa fedha kutoka balance yake
# ══════════════════════════════════════════════════════════════

class WithdrawalRequestViewSet(viewsets.ModelViewSet):
    """
    /api/payments/withdrawals/

    - Client: anaona TU maombi yake mwenyewe, anaweza kuunda mapya (POST).
    - Superadmin: anaona maombi YOTE ya clients wote, na anaweza
      approve/reject (PENGINE kupitia /approve/ na /reject/ actions).

    MUHIMU: hakuna PUT/PATCH/DELETE ya moja kwa moja — mabadiliko ya
    status yanafanyika TU kupitia actions za approve/reject, ili balance
    isipungue kwa bahati mbaya kupitia edit ya kawaida.
    """
    serializer_class = WithdrawalRequestSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        if self.request.user.is_superadmin():
            qs = WithdrawalRequest.objects.select_related('client', 'processed_by').all()
        else:
            qs = WithdrawalRequest.objects.select_related('client', 'processed_by').filter(
                client__user=self.request.user
            )

        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        return qs

    def perform_create(self, serializer):
        from apps.notifications.models import Notification
        from apps.accounts.models import User
        from apps.sms.at_service import send_at_sms

        client = self.request.user.client_profile
        withdrawal = serializer.save(client=client)

        message = (
            f"{client.business_name} ameomba kutoa TZS {withdrawal.amount:,.0f} "
            f"kupitia {withdrawal.get_network_display()} ({withdrawal.lipa_number}) — "
            f"Mtoaji: {withdrawal.account_name}."
        )

        # Arifa kwa admin (client=None → inaonekana kwa super admin pekee)
        Notification.objects.create(
            client=None,
            title='Ombi jipya la kutoa fedha',
            message=message,
            level='info',
            link='/admin/requests',
        )

        # SMS kwa admin(s) wote wenye namba ya simu (Africa's Talking,
        # one-way) — nyongeza ya notification ya in-app hapo juu. Njia
        # huru, haiathiri wala haitumii queue ya GSM (OutgoingSMS) kabisa.
        admin_phones = (
            User.objects.filter(role=User.ROLE_SUPERADMIN)
            .exclude(phone='')
            .values_list('phone', flat=True)
        )
        for phone in admin_phones:
            try:
                send_at_sms(phone, f"NetSafi: {message}")
            except Exception as e:
                logger.error(f"Withdrawal AT SMS imeshindwa kwa {phone}: {e}")

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        from apps.clients.models import Client
        from apps.notifications.models import Notification

        if not request.user.is_superadmin():
            return Response({'error': 'Huna ruhusa ya kufanya hivi'}, status=403)

        withdrawal = self.get_object()

        if withdrawal.status != WithdrawalRequest.STATUS_PENDING:
            return Response({'error': 'Ombi hili tayari limeshughulikiwa'}, status=400)

        client = withdrawal.client

        # Angalia tena balance ya SASA (inaweza kuwa imebadilika tangu
        # ombi liliundwa) — kuzuia kupitisha balance hasi.
        if withdrawal.amount > client.balance:
            return Response(
                {'error': f'Balance ya {client.business_name} haitoshi tena. Bakaa ya sasa: TZS {client.balance:,.0f}'},
                status=400
            )

        # Punguza balance HAPA PEKEE — hii ndiyo hatua pekee
        # inayogusa balance kwenye mzunguko mzima wa withdrawal.
        Client.objects.filter(pk=client.pk).update(balance=F('balance') - withdrawal.amount)

        withdrawal.status = WithdrawalRequest.STATUS_APPROVED
        withdrawal.processed_by = request.user
        withdrawal.processed_at = timezone.now()
        withdrawal.save(update_fields=['status', 'processed_by', 'processed_at'])

        Notification.objects.create(
            client=client,
            title='Ombi la kutoa fedha limekubaliwa',
            message=f"Ombi lako la TZS {withdrawal.amount:,.0f} limekubaliwa na linashughulikiwa.",
            level='success',
            link='/client/withdraw',
        )

        return Response(WithdrawalRequestSerializer(withdrawal).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        from apps.notifications.models import Notification

        if not request.user.is_superadmin():
            return Response({'error': 'Huna ruhusa ya kufanya hivi'}, status=403)

        withdrawal = self.get_object()

        if withdrawal.status != WithdrawalRequest.STATUS_PENDING:
            return Response({'error': 'Ombi hili tayari limeshughulikiwa'}, status=400)

        note = (request.data.get('note') or '').strip()

        withdrawal.status = WithdrawalRequest.STATUS_REJECTED
        withdrawal.admin_note = note
        withdrawal.processed_by = request.user
        withdrawal.processed_at = timezone.now()
        withdrawal.save(update_fields=['status', 'admin_note', 'processed_by', 'processed_at'])

        message = f"Ombi lako la TZS {withdrawal.amount:,.0f} limekataliwa."
        if note:
            message += f" Sababu: {note}"

        Notification.objects.create(
            client=withdrawal.client,
            title='Ombi la kutoa fedha limekataliwa',
            message=message,
            level='error',
            link='/client/withdraw',
        )

        return Response(WithdrawalRequestSerializer(withdrawal).data)

