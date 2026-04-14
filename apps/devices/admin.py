from django.contrib import admin
from .models import GSMDevice
@admin.register(GSMDevice)
class GSMDeviceAdmin(admin.ModelAdmin):
    list_display = ['name','network','lipa_number','phone_number','is_active','last_seen']
    list_filter = ['network','is_active']
    readonly_fields = ['last_seen','created_at','updated_at']
