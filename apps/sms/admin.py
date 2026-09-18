from django.contrib import admin
from .models import OutgoingSMS


@admin.register(OutgoingSMS)
class OutgoingSMSAdmin(admin.ModelAdmin):
    list_display = ['phone', 'client', 'status', 'priority', 'retries', 'created_at', 'sent_at']
    list_filter = ['status', 'client']
    search_fields = ['phone', 'message', 'client__business_name']
    readonly_fields = ['created_at', 'sent_at']
    ordering = ['-priority', 'created_at']
