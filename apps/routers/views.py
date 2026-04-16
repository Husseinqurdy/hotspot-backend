import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from .models import MikroTikRouter, MikroTikJob
from .serializers import RouterSerializer, JobSerializer
from .mikrotik import get_mikrotik_connection

logger = logging.getLogger('netsafi')

class RouterViewSet(viewsets.ModelViewSet):
    serializer_class = RouterSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        if self.request.user.is_superadmin():
            return MikroTikRouter.objects.select_related('client').all()
        return MikroTikRouter.objects.filter(client__user=self.request.user).select_related('client')
    def perform_create(self, serializer):
        if self.request.user.is_client():
            from apps.clients.models import Client
            serializer.save(client=Client.objects.get(user=self.request.user))
        else:
            serializer.save()
    def destroy(self, request, *args, **kwargs):
        router = self.get_object()
        if request.user.is_client() and router.client.user != request.user:
            return Response(status=403)
        router.delete()
        return Response(status=204)

    @action(detail=True, methods=['post'], url_path='test-connection')
    def test_connection(self, request, pk=None):
        router = self.get_object()
        api = get_mikrotik_connection(router)
        if api and api.is_alive():
            identity = api.get_identity()
            api.disconnect()
            router.is_online = True; router.last_seen = timezone.now()
            router.save(update_fields=['is_online','last_seen'])
            return Response({'status':'online','message':f'{router.name} inapatikana','identity':identity})
        router.is_online = False; router.save(update_fields=['is_online'])
        return Response({'status':'offline','message':'Haiwezekani kuunganika'}, status=400)

    @action(detail=True, methods=['post'], url_path='sync-packages')
    def sync_packages(self, request, pk=None):
        router = self.get_object()
        api = get_mikrotik_connection(router)
        if not api: return Response({'error':'Router offline'}, status=400)
        from apps.packages.models import Package
        packages = Package.objects.filter(client=router.client, is_active=True)
        synced = 0
        for p in packages:
            if api.add_hotspot_profile(p.mikrotik_profile, f"{p.speed_up}M/{p.speed_down}M", f"{p.duration_minutes}m", p.shared_users):
                synced += 1
        api.disconnect()
        return Response({'message':f'Profiles {synced} zimesync','total':packages.count()})

    @action(detail=False, methods=['get'], url_path='pending-jobs')
    def pending_jobs(self, request):
        jobs = MikroTikJob.objects.filter(status__in=['pending','processing']).select_related('router','package')[:20]
        if request.user.is_client():
            jobs = jobs.filter(client__user=request.user)
        return Response(JobSerializer(jobs, many=True).data)
