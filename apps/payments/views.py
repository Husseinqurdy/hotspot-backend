from django.db.models import Sum, Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Payment
from .serializers import PaymentSerializer


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