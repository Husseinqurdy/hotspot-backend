from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    level_display = serializers.CharField(source='get_level_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'level', 'level_display',
            'link', 'is_read', 'created_at',
        ]

