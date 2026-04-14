from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Client
from .serializers import ClientSerializer, ClientCreateSerializer, AddBalanceSerializer

class ClientViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        if self.request.user.is_superadmin():
            return Client.objects.select_related('user').all()
        return Client.objects.filter(user=self.request.user)
    def get_serializer_class(self):
        return ClientCreateSerializer if self.action == 'create' else ClientSerializer
    def create(self, request, *args, **kwargs):
        if not request.user.is_superadmin():
            return Response({'error': 'Superadmin peke yake'}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = serializer.save()
        return Response(ClientSerializer(client).data, status=status.HTTP_201_CREATED)
    def destroy(self, request, *args, **kwargs):
        if not request.user.is_superadmin():
            return Response(status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)
    @action(detail=True, methods=['post'], url_path='add-balance')
    def add_balance(self, request, pk=None):
        if not request.user.is_superadmin():
            return Response(status=status.HTTP_403_FORBIDDEN)
        client = self.get_object()
        serializer = AddBalanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']
        client.balance += amount
        client.save(update_fields=['balance'])
        return Response({'message': f'TZS {amount} imeongezwa', 'new_balance': str(client.balance)})
