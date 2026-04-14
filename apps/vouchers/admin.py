from django.contrib import admin
from .models import Voucher
@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ['code','client','package','customer_phone','status','created_at']
    list_filter = ['status','client']
    readonly_fields = ['code','created_at']
