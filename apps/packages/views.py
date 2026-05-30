from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Package
from .serializers import PackageSerializer
class PackageViewSet(viewsets.ModelViewSet):
    serializer_class = PackageSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        qs = Package.objects.select_related('client').all() if self.request.user.is_superadmin() else Package.objects.filter(client__user=self.request.user)
        if cid := self.request.query_params.get('client'): qs = qs.filter(client_id=cid)
        return qs
    def perform_create(self, serializer):
        if self.request.user.is_client():
            from apps.clients.models import Client
            serializer.save(client=Client.objects.get(user=self.request.user))
        else: serializer.save()