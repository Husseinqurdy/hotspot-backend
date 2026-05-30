from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Voucher
from .serializers import VoucherSerializer
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