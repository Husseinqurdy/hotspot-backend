from django.contrib import admin

from .models import GSMDevice


@admin.register(GSMDevice)
class GSMDeviceAdmin(admin.ModelAdmin):
    list_display = ['device_id', 'status', 'name', 'client', 'network', 'lipa_number', 'shared_with_display', 'is_active', 'last_seen']
    list_filter = ['status', 'network', 'is_active', 'client']
    search_fields = ['name', 'lipa_number', 'phone_number', 'device_id', 'client__business_name']
    autocomplete_fields = ['client', 'shared_with']
    readonly_fields = ['status', 'api_key', 'last_seen', 'created_at', 'updated_at']

    def shared_with_display(self, obj):
        names = [c.business_name for c in obj.shared_with.all()]
        return ', '.join(names) if names else '—'
    shared_with_display.short_description = 'Shared na'
