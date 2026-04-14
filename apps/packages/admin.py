from django.contrib import admin
from .models import Package
@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ['name','client','price','duration_display','is_active']
