from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.hashers import make_password
from .models import Client, MIKROTIK_FEATURES
from .serializers import ClientSerializer, ClientCreateSerializer, AddBalanceSerializer, ChangePasswordSerializer


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
            return Response({'error': 'Superadmin peke yake'}, status=403)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = serializer.save()
        return Response(ClientSerializer(client).data, status=201)

    def update(self, request, *args, **kwargs):
        if not request.user.is_superadmin():
            return Response(status=403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_superadmin():
            return Response(status=403)
        client = self.get_object()
        client.user.delete()  # Deletes client too via cascade
        return Response(status=204)

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        if not request.user.is_superadmin():
            return Response(status=403)
        client = self.get_object()
        client.is_active = True
        client.user.is_active = True
        client.save(update_fields=['is_active'])
        client.user.save(update_fields=['is_active'])
        return Response({'message': f'{client.business_name} imeactiviwa'})

    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        if not request.user.is_superadmin():
            return Response(status=403)
        client = self.get_object()
        client.is_active = False
        client.user.is_active = False
        client.save(update_fields=['is_active'])
        client.user.save(update_fields=['is_active'])
        return Response({'message': f'{client.business_name} imezuiwa'})

    @action(detail=True, methods=['post'], url_path='change-password')
    def change_password(self, request, pk=None):
        if not request.user.is_superadmin():
            return Response(status=403)
        client = self.get_object()
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client.user.password = make_password(serializer.validated_data['new_password'])
        client.user.save(update_fields=['password'])
        return Response({'message': 'Password imebadilishwa'})

    @action(detail=True, methods=['post'], url_path='add-balance')
    def add_balance(self, request, pk=None):
        if not request.user.is_superadmin():
            return Response(status=403)
        client = self.get_object()
        serializer = AddBalanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']
        client.balance += amount
        client.save(update_fields=['balance'])
        return Response({'message': f'TZS {amount} imeongezwa', 'new_balance': str(client.balance)})

    @action(detail=True, methods=['post'], url_path='mikrotik-permissions')
    def mikrotik_permissions(self, request, pk=None):
        """Weka permissions za MikroTik kwa client."""
        if not request.user.is_superadmin():
            return Response(status=403)
        client = self.get_object()
        permissions = request.data.get('permissions', [])
        # Validate — ruhusu tu features zinazojulikana
        valid = [p for p in permissions if p in MIKROTIK_FEATURES]
        client.mikrotik_permissions = valid
        client.save(update_fields=['mikrotik_permissions'])
        return Response({
            'message': f'Permissions za {client.business_name} zimesasishwa',
            'mikrotik_permissions': valid
        })

    @action(detail=False, methods=['get'], url_path='my-mikrotik-permissions')
    def my_mikrotik_permissions(self, request):
        """Client apate permissions zake mwenyewe."""
        try:
            client = Client.objects.get(user=request.user)
            return Response({
                'mikrotik_permissions': client.mikrotik_permissions or [],
                'all_features': MIKROTIK_FEATURES,
            })
        except Client.DoesNotExist:
            # Superadmin ana access yote
            if request.user.is_superadmin():
                return Response({
                    'mikrotik_permissions': MIKROTIK_FEATURES,
                    'all_features': MIKROTIK_FEATURES,
                })
            return Response({'mikrotik_permissions': [], 'all_features': MIKROTIK_FEATURES})