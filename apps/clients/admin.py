from django.contrib import admin
from .models import Client
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['business_name','reference_prefix','balance','commission_rate','is_active']
    readonly_fields = ['reference_prefix','created_at','updated_at']
