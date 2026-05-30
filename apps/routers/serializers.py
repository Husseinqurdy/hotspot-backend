from rest_framework import serializers
from .models import MikroTikRouter, MikroTikJob

class RouterSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.business_name', read_only=True)
    class Meta:
        model = MikroTikRouter
        fields = ['id','client','client_name','name','host','api_port','api_username','api_password','hotspot_interface','is_online','last_seen','created_at','updated_at']
        extra_kwargs = {'api_password': {'write_only': True}}

class JobSerializer(serializers.ModelSerializer):
    router_name = serializers.CharField(source='router.name', read_only=True)
    package_name = serializers.CharField(source='package.name', read_only=True)
    class Meta:
        model = MikroTikJob
        fields = ['id','router_name','package_name','action','status','voucher_code','customer_phone','retries','created_at','completed_at']
        read_only_fields = fields