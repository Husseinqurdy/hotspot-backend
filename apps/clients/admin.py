from django.contrib import admin
from .models import Client

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['business_name', 'identifier', 'balance', 'commission_rate', 'is_active', 'created_at']
    readonly_fields = ['identifier', 'created_at']
    search_fields = ['business_name', 'user__username']
    list_filter = ['is_active']