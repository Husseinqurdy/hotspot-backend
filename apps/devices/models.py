from django.db import models
class GSMDevice(models.Model):
    NETWORK_CHOICES = [('vodacom','Vodacom M-Pesa'),('tigo','Tigo Pesa'),('airtel','Airtel Money'),('halo','HaloPesa')]
    name = models.CharField(max_length=100)
    network = models.CharField(max_length=20, choices=NETWORK_CHOICES, unique=True)
    lipa_number = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=20)
    device_id = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: ordering = ['network']
    def __str__(self): return f"{self.name} ({self.get_network_display()}) - {self.lipa_number}"
