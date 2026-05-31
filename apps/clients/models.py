from django.db import models
from django.db import transaction
from apps.accounts.models import User


def generate_identifier():
    with transaction.atomic():
        last = Client.objects.select_for_update().order_by('-identifier').first()
        if last and last.identifier:
            return last.identifier + 1
        return 1


# Features zote za MikroTik Manager
MIKROTIK_FEATURES = [
    'servers',
    'server_profiles',
    'users',
    'active',
    'hosts',
    'ip_bindings',
    'walled_garden',
    'walled_garden_ip',
    'cookies',
    'scheduler',
]


class Client(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='client_profile'
    )
    business_name = models.CharField(max_length=100)
    identifier = models.PositiveIntegerField(
        unique=True,
        editable=False,
        null=True,
        blank=True
    )
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00
    )
    is_active = models.BooleanField(default=True)

    # Permissions za MikroTik — list ya features zilizoruhusiwa
    # Kama field iko tupu (None au []), client hawezi kuona chochote
    # Kama ina ['servers', 'users', ...], anaona hizo tu
    mikrotik_permissions = models.JSONField(
        default=list,
        blank=True,
        help_text="Features za MikroTik ambazo client amepewa ruhusa"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.identifier:
            self.identifier = generate_identifier()
        super().save(*args, **kwargs)

    def has_mikrotik_permission(self, feature: str) -> bool:
        """Angalia kama client ana ruhusa ya feature fulani."""
        return feature in (self.mikrotik_permissions or [])

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.business_name} [ID: {self.identifier}]"