from django.db import models
from apps.clients.models import Client
class Payment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [(STATUS_PENDING,'Inasubiri'),(STATUS_PROCESSING,'Inachakatwa'),(STATUS_COMPLETED,'Imekamilika'),(STATUS_FAILED,'Imeshindwa')]
    NETWORK_CHOICES = [('vodacom','Vodacom M-Pesa'),('tigo','Tigo Pesa'),('airtel','Airtel Money'),('halo','HaloPesa'),('unknown','Haijulikani')]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='payments')
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference_code = models.CharField(max_length=20)
    network = models.CharField(max_length=20, choices=NETWORK_CHOICES, default='unknown')
    device_id = models.CharField(max_length=50, blank=True)
    raw_sms = models.TextField()
    sms_hash = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    client_share = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: ordering = ['-created_at']
    def __str__(self): return f"{self.client} | TZS {self.amount} | {self.status}"
