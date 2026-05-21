from django.contrib import admin
from .models import Voucher


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ['code', 'client', 'package', 'customer_phone', 'status', 'created_at', 'expires_at']
    list_filter = ['status', 'client']
    search_fields = ['code', 'customer_phone', 'client__business_name']
    readonly_fields = ['code', 'created_at', 'used_at', 'expires_at']