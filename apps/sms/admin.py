from django.contrib import admin
from .models import SMSLog, OutgoingSMS

@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ['phone_number','status','created_at']
    list_filter = ['status']
    readonly_fields = ['phone_number','message','status','created_at']

@admin.register(OutgoingSMS)
class OutgoingSMSAdmin(admin.ModelAdmin):
    list_display = ['phone','status','priority','retries','created_at','sent_at']
    list_filter = ['status']
    readonly_fields = ['created_at','sent_at']
