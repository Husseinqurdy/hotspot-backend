from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Super admin: anaona notifications za client=None (mfumo) TU.
    Client: anaona notifications za client wake mwenyewe TU.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superadmin():
            qs = Notification.objects.filter(client__isnull=True)
        else:
            qs = Notification.objects.filter(client__user=user)

        unread_only = self.request.query_params.get('unread')
        if unread_only == 'true':
            qs = qs.filter(is_read=False)
        return qs

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'message': f'{updated} notifications zimesomwa'})

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response({'message': 'Imesomwa'})

