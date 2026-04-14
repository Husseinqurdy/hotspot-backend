from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import GSMDevice
from .serializers import GSMDeviceSerializer, GSMDevicePublicSerializer

class GSMDeviceViewSet(viewsets.ModelViewSet):
    queryset = GSMDevice.objects.all()
    serializer_class = GSMDeviceSerializer
    permission_classes = [IsAuthenticated]
    def create(self, request, *args, **kwargs):
        if not request.user.is_superadmin(): return Response({'error':'Superadmin peke yake'}, status=403)
        return super().create(request, *args, **kwargs)
    def update(self, request, *args, **kwargs):
        if not request.user.is_superadmin(): return Response(status=403)
        return super().update(request, *args, **kwargs)
    def destroy(self, request, *args, **kwargs):
        if not request.user.is_superadmin(): return Response(status=403)
        return super().destroy(request, *args, **kwargs)
    @action(detail=False, methods=['get'], url_path='public')
    def public_list(self, request):
        devices = GSMDevice.objects.filter(is_active=True).order_by('network')
        return Response(GSMDevicePublicSerializer(devices, many=True).data)
