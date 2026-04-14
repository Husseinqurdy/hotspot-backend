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
        qs = Payment.objects.select_related('client').all() if self.request.user.is_superadmin() else Payment.objects.filter(client__user=self.request.user)
        for f,k in [('status','status'),('network','network'),('date_from','created_at__date__gte'),('date_to','created_at__date__lte')]:
            if v := self.request.query_params.get(f): qs = qs.filter(**{k:v})
        return qs
    @action(detail=False, methods=['get'])
    def summary(self, request):
        qs = self.get_queryset().filter(status='completed')
        by_network = {}
        for p in qs: by_network[p.network] = by_network.get(p.network,0) + float(p.amount)
        return Response({'total_payments':qs.count(),'total_amount':str(sum(p.amount for p in qs)),'total_commission':str(sum(p.commission_amount for p in qs)),'total_client_share':str(sum(p.client_share for p in qs)),'by_network':by_network})
