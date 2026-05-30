from rest_framework import serializers
from .models import GSMDevice
class GSMDeviceSerializer(serializers.ModelSerializer):
    network_display = serializers.CharField(source='get_network_display', read_only=True)
    class Meta:
        model = GSMDevice
        fields = ['id','name','network','network_display','lipa_number','phone_number','device_id','description','is_active','last_seen','created_at']
        read_only_fields = ['id','last_seen','created_at']
class GSMDevicePublicSerializer(serializers.ModelSerializer):
    network_display = serializers.CharField(source='get_network_display', read_only=True)
    class Meta:
        model = GSMDevice
        fields = ['network','network_display','lipa_number']