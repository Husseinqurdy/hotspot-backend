from django.db import models
from apps.clients.models import Client


class Package(models.Model):
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='packages'
    )
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_minutes = models.IntegerField()
    speed_up = models.CharField(max_length=10, default='2')
    speed_down = models.CharField(max_length=10, default='2')
    mikrotik_profile = models.CharField(max_length=50)
    shared_users = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['price']
        unique_together = ['client', 'name']

    def __str__(self):
        return f"{self.name} - TZS {self.price}"

    def duration_display(self):
        if self.duration_minutes < 60:
            return f"Dakika {self.duration_minutes}"
        elif self.duration_minutes < 1440:
            return f"Saa {self.duration_minutes // 60}"
        return f"Siku {self.duration_minutes // 1440}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # Kama si mpya, angalia kama price imebadilika
        if not is_new:
            try:
                old = Package.objects.get(pk=self.pk)
                price_changed = old.price != self.price
            except Package.DoesNotExist:
                price_changed = False
        else:
            price_changed = False

        super().save(*args, **kwargs)

        from apps.payments.models import ClientPackagePrice
        new_unique_amount = int(self.price) + self.client.identifier

        if is_new:
            # Package mpya — unda ClientPackagePrice
            ClientPackagePrice.objects.create(
                client=self.client,
                package=self,
                unique_amount=new_unique_amount
            )
        elif price_changed:
            # Price imebadilika — update unique_amount
            ClientPackagePrice.objects.filter(
                client=self.client,
                package=self
            ).update(unique_amount=new_unique_amount)