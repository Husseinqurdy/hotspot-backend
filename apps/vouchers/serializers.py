from rest_framework import serializers
from .models import Voucher
class VoucherSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.business_name', read_only=True)
    router_name = serializers.CharField(source='router.name', read_only=True)
    package_name = serializers.CharField(source='package.name', read_only=True)
    package_price = serializers.DecimalField(source='package.price', max_digits=10, decimal_places=2, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    class Meta:
        model = Voucher
        fields = ['id','client','client_name','router_name','package_name','package_price','code','customer_phone','status','status_display','created_at','used_at','expires_at']
        read_only_fields = fields
