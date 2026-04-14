from django.db import models
from django.utils import timezone
from apps.clients.models import Client
from apps.routers.models import MikroTikRouter
from apps.packages.models import Package
from apps.payments.models import Payment

class Voucher(models.Model):
    STATUS_CHOICES = [('active','Active'),('used','Imetumika'),('expired','Imeisha')]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='vouchers')
    router = models.ForeignKey(MikroTikRouter, on_delete=models.CASCADE)
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, null=True)
    code = models.CharField(max_length=20, unique=True, db_index=True)
    customer_phone = models.CharField(max_length=15)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    class Meta: ordering = ['-created_at']
    def save(self, *args, **kwargs):
        if not self.expires_at and self.package_id:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=self.package.duration_minutes*2)
        super().save(*args, **kwargs)
    def __str__(self): return f"{self.code} | {self.status}"
