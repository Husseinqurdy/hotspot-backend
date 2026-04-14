from django.contrib import admin
from .models import MikroTikRouter, MikroTikJob

@admin.register(MikroTikRouter)
class RouterAdmin(admin.ModelAdmin):
    list_display = ['name','client','host','api_port','is_online','last_seen']
    list_filter = ['is_online','client']
    readonly_fields = ['is_online','last_seen','created_at']

@admin.register(MikroTikJob)
class JobAdmin(admin.ModelAdmin):
    list_display = ['id','router','status','customer_phone','voucher_code','retries','created_at']
    list_filter = ['status']
    readonly_fields = ['created_at','updated_at','completed_at']
