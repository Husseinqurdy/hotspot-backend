from django.db import models
from apps.clients.models import Client
from apps.packages.models import Package


class ClientPackagePrice(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='package_prices')
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='client_prices')
    unique_amount = models.PositiveIntegerField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Client Package Price"
        verbose_name_plural = "Client Package Prices"
        ordering = ['unique_amount']

    def __str__(self):
        return f"{self.client} | {self.package} | {self.unique_amount}"


class Payment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_DUPLICATE = 'duplicate'
    STATUS_INVALID = 'invalid'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_DUPLICATE, 'Duplicate'),
        (STATUS_INVALID, 'Invalid'),
    ]

    NETWORK_VODACOM = 'vodacom'
    NETWORK_TIGO = 'tigo'
    NETWORK_AIRTEL = 'airtel'
    NETWORK_HALO = 'halo'
    NETWORK_UNKNOWN = 'unknown'

    NETWORK_CHOICES = [
        (NETWORK_VODACOM, 'Vodacom M-Pesa'),
        (NETWORK_TIGO, 'Tigo Pesa'),
        (NETWORK_AIRTEL, 'Airtel Money'),
        (NETWORK_HALO, 'HaloPesa'),
        (NETWORK_UNKNOWN, 'Unknown'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='payments')
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    client_package_price = models.ForeignKey(ClientPackagePrice, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=20)
    amount = models.PositiveIntegerField()
    network = models.CharField(max_length=20, choices=NETWORK_CHOICES, default=NETWORK_UNKNOWN)
    device_id = models.CharField(max_length=100, blank=True, null=True)
    raw_sms = models.TextField()
    sms_hash = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    client_share = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['amount']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['network']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.client} | {self.amount} TZS | {self.status}"