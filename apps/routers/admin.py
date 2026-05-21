from django.contrib import admin
from .models import MikroTikRouter, MikroTikJob


@admin.register(MikroTikRouter)
class RouterAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'host', 'is_online', 'last_seen', 'created_at']
    list_filter = ['is_online', 'client']
    search_fields = ['name', 'host', 'client__business_name']
    readonly_fields = ['is_online', 'last_seen', 'created_at', 'updated_at']


@admin.register(MikroTikJob)
class JobAdmin(admin.ModelAdmin):
    list_display = ['id', 'router', 'package', 'status', 'customer_phone', 'retries', 'created_at']
    list_filter = ['status', 'action']
    search_fields = ['customer_phone', 'voucher_code', 'router__name']
    readonly_fields = ['created_at', 'completed_at', 'updated_at']