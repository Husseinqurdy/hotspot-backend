from django.contrib import admin

from .models import Payment, ClientPackagePrice


@admin.register(ClientPackagePrice)
class ClientPackagePriceAdmin(admin.ModelAdmin):

    list_display = [
        'client',
        'package',
        'unique_amount',
        'is_active',
        'created_at',
    ]

    list_filter = [
        'is_active',
        'package',
    ]

    search_fields = [
        'client__business_name',
        'unique_amount',
    ]

    ordering = [
        'unique_amount'
    ]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    list_display = [
        'id',
        'client',
        'package',
        'phone_number',
        'amount',
        'network',
        'status',
        'transaction_id',
        'created_at',
    ]

    list_filter = [
        'status',
        'network',
        'created_at',
    ]

    search_fields = [
        'phone_number',
        'transaction_id',
        'client__business_name',
        'amount',
    ]

    readonly_fields = [
        'sms_hash',
        'created_at',
        'processed_at',
        'raw_sms',
    ]

    ordering = [
        '-created_at'
    ]

    list_per_page = 50

    fieldsets = (

        ('Client Information', {
            'fields': (
                'client',
                'package',
                'client_package_price',
            )
        }),

        ('Payment Information', {
            'fields': (
                'phone_number',
                'amount',
                'transaction_id',
                'network',
                'device_id',
                'status',
            )
        }),

        ('Money Split', {
            'fields': (
                'commission_amount',
                'client_share',
            )
        }),

        ('SMS Data', {
            'fields': (
                'raw_sms',
                'sms_hash',
            )
        }),

        ('Timestamps', {
            'fields': (
                'created_at',
                'processed_at',
            )
        }),
    )