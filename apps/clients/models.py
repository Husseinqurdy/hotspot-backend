import random, string
from django.db import models
from apps.accounts.models import User

def generate_unique_prefix():
    while True:
        prefix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if not Client.objects.filter(reference_prefix=prefix).exists():
            return prefix

class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    business_name = models.CharField(max_length=100)
    reference_prefix = models.CharField(max_length=4, unique=True, editable=False)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def save(self, *args, **kwargs):
        if not self.reference_prefix:
            self.reference_prefix = generate_unique_prefix()
        super().save(*args, **kwargs)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"{self.business_name} [{self.reference_prefix}]"
