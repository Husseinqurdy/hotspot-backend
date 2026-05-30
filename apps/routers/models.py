from django.db import models
from apps.clients.models import Client

class MikroTikRouter(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='routers')
    name = models.CharField(max_length=100)
    host = models.CharField(max_length=100, help_text='VPN IP (10.66.66.x) au DDNS')
    api_port = models.IntegerField(default=8728)
    api_username = models.CharField(max_length=50, default='admin')
    api_password = models.CharField(max_length=100)
    hotspot_interface = models.CharField(max_length=50, default='bridge')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: ordering = ['-created_at']
    def __str__(self): return f"{self.name} ({self.client.business_name})"

class MikroTikJob(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [(STATUS_PENDING,'Inasubiri'),(STATUS_PROCESSING,'Inachakatwa'),(STATUS_COMPLETED,'Imekamilika'),(STATUS_FAILED,'Imeshindwa')]
    ACTION_CREATE_VOUCHER = 'create_voucher'
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='jobs')
    router = models.ForeignKey(MikroTikRouter, on_delete=models.CASCADE)
    package = models.ForeignKey('packages.Package', on_delete=models.CASCADE)
    payment = models.ForeignKey('payments.Payment', on_delete=models.CASCADE, null=True)
    action = models.CharField(max_length=50, default=ACTION_CREATE_VOUCHER)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    voucher_code = models.CharField(max_length=20, blank=True)
    customer_phone = models.CharField(max_length=15)
    error_message = models.TextField(blank=True)
    retries = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    class Meta: ordering = ['created_at']
    def __str__(self): return f"Job {self.id} | {self.status}"