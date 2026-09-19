from rest_framework import serializers

from .models import GSMDevice


class GSMDeviceSerializer(serializers.ModelSerializer):
    network_display = serializers.CharField(source='get_network_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    client_name = serializers.CharField(source='client.business_name', read_only=True)
    shared_with_names = serializers.SerializerMethodField()

    class Meta:
        model = GSMDevice
        fields = [
            'id', 'status', 'status_display',
            'client', 'client_name', 'shared_with', 'shared_with_names',
            'name', 'network', 'network_display',
            'lipa_number', 'phone_number', 'device_id', 'api_key',
            'description', 'is_active', 'last_seen', 'created_at',
            'pending_restart', 'pending_sim_reset',
            'battery_percent', 'on_backup_power', 'last_rssi',
        ]
        read_only_fields = ['id', 'status', 'api_key', 'last_seen', 'created_at']

    def get_shared_with_names(self, obj):
        return [c.business_name for c in obj.shared_with.all()]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        # Ficha api_key kwenye list/retrieve za kawaida — ionyeshwe tu
        # mara moja mara baada ya create (POST) au claim.
        if request and request.method == 'POST':
            pass  # onyesha kamili
        elif data.get('api_key'):
            data['api_key'] = '••••••••' + instance.api_key[-4:]
        return data


class GSMDevicePublicSerializer(serializers.ModelSerializer):
    """
    Inatumika na public_list endpoint — HAINA client wala api_key,
    ni kwa ajili ya kuonyesha lipa namba kwa umma.
    """
    network_display = serializers.CharField(source='get_network_display', read_only=True)

    class Meta:
        model = GSMDevice
        fields = ['network', 'network_display', 'lipa_number']
