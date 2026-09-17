from django.db import models, transaction
from django.core.exceptions import ValidationError
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

    def clean(self):
        """Validate unique_amount conflict kabla ya kuhifadhi"""
        if not self.client_id:
            return

        try:
            from apps.payments.models import ClientPackagePrice
            new_unique_amount = int(self.price) + self.client.identifier

            conflict = ClientPackagePrice.objects.filter(
                unique_amount=new_unique_amount
            ).exclude(package=self).first()

            if conflict:
                raise ValidationError({
                    'price': (
                        f"Bei hii inasababisha mgongano! Kiasi {new_unique_amount} "
                        f"tayari kinatumika na '{conflict.client.business_name}' "
                        f"kwenye package '{conflict.package.name}'. "
                        f"Tafadhali badilisha bei yako."
                    )
                })
        except ImportError:
            pass

    def save(self, *args, **kwargs):
        # Angalia kama price imebadilika (kwa package zilizopo)
        is_new = self.pk is None
        price_changed = False

        if not is_new:
            try:
                old = Package.objects.get(pk=self.pk)
                price_changed = old.price != self.price
            except Package.DoesNotExist:
                pass

        # ✅ Validate kwanza kabla ya kuhifadhi chochote
        self.full_clean()

        # ✅ Yote yanafanyika pamoja — yakifail yote yanarudishwa nyuma
        with transaction.atomic():
            super().save(*args, **kwargs)

            from apps.payments.models import ClientPackagePrice
            new_unique_amount = int(self.price) + self.client.identifier

            if is_new:
                ClientPackagePrice.objects.create(
                    client=self.client,
                    package=self,
                    unique_amount=new_unique_amount
                )
            elif price_changed:
                ClientPackagePrice.objects.filter(
                    client=self.client,
                    package=self
                ).update(unique_amount=new_unique_amount)