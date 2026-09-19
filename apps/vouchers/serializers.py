from rest_framework import serializers
from .models import Voucher
from .models import VoucherPrintBatch, DailySalesReport

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

class VoucherPrintBatchSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(source='package.name', read_only=True, default='')
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = VoucherPrintBatch
        fields = [
            'id', 'profile_name', 'package_name', 'unit_price',
            'quantity', 'theme', 'pdf_url', 'created_at',
        ]

    def get_pdf_url(self, obj):
        if not obj.pdf_file:
            return None
        request = self.context.get('request')
        url = obj.pdf_file.url
        return request.build_absolute_uri(url) if request else url


class DailySalesReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailySalesReport
        fields = ['id', 'date', 'total_vouchers_sold', 'total_revenue', 'breakdown', 'created_at']

