from rest_framework import serializers
from .models import Package
class PackageSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.business_name', read_only=True)
    duration_display = serializers.CharField(read_only=True)
    class Meta:
        model = Package
        fields = ['id','client','client_name','name','price','duration_minutes','duration_display','speed_up','speed_down','mikrotik_profile','shared_users','is_active','created_at']
        read_only_fields = ['id','created_at']