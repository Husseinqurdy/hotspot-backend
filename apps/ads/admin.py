from django.contrib import admin
from .models import Advertiser, Advertisement, AdImpression, SponsoredAccessLog


@admin.register(Advertiser)
class AdvertiserAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_phone', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'contact_phone', 'contact_email']


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'advertiser', 'ad_type', 'is_active',
        'sponsored_minutes', 'cooldown_hours', 'priority', 'start_date', 'end_date',
    ]
    list_filter = ['ad_type', 'is_active']
    search_fields = ['title', 'advertiser__name']
    filter_horizontal = ['routers']


@admin.register(AdImpression)
class AdImpressionAdmin(admin.ModelAdmin):
    list_display = ['ad', 'router', 'client_mac', 'shown_at', 'clicked']
    list_filter = ['clicked', 'router']
    search_fields = ['client_mac']
    readonly_fields = ['shown_at']


@admin.register(SponsoredAccessLog)
class SponsoredAccessLogAdmin(admin.ModelAdmin):
    list_display = ['client_mac', 'ad', 'router', 'minutes_granted', 'granted_at', 'expires_at']
    list_filter = ['router', 'ad']
    search_fields = ['client_mac']
    readonly_fields = ['granted_at']

