from django.contrib import admin
from .models import Payment
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['client','phone_number','amount','network','status','created_at']
    list_filter = ['status','network']
    readonly_fields = ['sms_hash','created_at']
