from django.contrib import admin
from .models import Package


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'price', 'duration_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'client']
    search_fields = ['name', 'client__business_name']
    readonly_fields = ['created_at']