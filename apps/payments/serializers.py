from rest_framework import serializers
from .models import Payment
class PaymentSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.business_name', read_only=True)
    network_display = serializers.CharField(source='get_network_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    class Meta:
        model = Payment
        fields = ['id','client','client_name','phone_number','amount','reference_code','network','network_display','status','status_display','commission_amount','client_share','created_at']
        read_only_fields = fields
