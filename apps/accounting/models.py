"""
Uhasibu — app ya pekee. Haina uhusiano wowote wa data na Payment, Voucher,
Router wala Client. Inashiriki tu authentication (User ya superadmin).
"""
from django.conf import settings
from django.db import models


class Site(models.Model):
    """Eneo la biashara (kawaida MikroTik moja). Linaundwa kwa mkono na mhasibu."""
    name = models.CharField(max_length=100, unique=True)
    note = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Entry(models.Model):
    INCOME, EXPENSE, ASSET, LIABILITY, LOAN, LOAN_PAYMENT = (
        'income', 'expense', 'asset', 'liability', 'loan', 'loan_payment')
    KINDS = [
        (INCOME, 'Mapato'), (EXPENSE, 'Matumizi'), (ASSET, 'Mali'),
        (LIABILITY, 'Deni'), (LOAN, 'Mkopo'), (LOAN_PAYMENT, 'Marejesho ya mkopo'),
    ]

    # site = None  → rekodi ya kampuni nzima
    site = models.ForeignKey(Site, null=True, blank=True, on_delete=models.PROTECT, related_name='entries')
    kind = models.CharField(max_length=15, choices=KINDS)
    date = models.DateField()
    category = models.CharField(max_length=80, blank=True)
    description = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # mkopo tu, taarifa
    loan_ref = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='payments')

    # Rekodi HAIFUTWI — inawekewa alama ya 'imefutwa' na inabaki kwenye vitabu.
    voided = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name='+')
    voided_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-id']
        indexes = [models.Index(fields=['kind', 'date']), models.Index(fields=['site', 'date'])]


class _ImmutableQuerySet(models.QuerySet):
    def delete(self):
        raise PermissionError('Logs za uhasibu haziwezi kufutwa.')

    def update(self, **kw):
        raise PermissionError('Logs za uhasibu haziwezi kubadilishwa.')


class AuditLog(models.Model):
    """Kumbukumbu isiyobadilika: nani, nini, wapi (site), lini, kabla/baada."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    username = models.CharField(max_length=150)          # nakala, jina likibaki hata user akifutwa
    action = models.CharField(max_length=30)
    target = models.CharField(max_length=60, blank=True)  # mfano 'entry:12'
    site_name = models.CharField(max_length=100, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = _ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at', '-id']

    def save(self, *a, **kw):
        if self.pk:
            raise PermissionError('Logs za uhasibu haziwezi kubadilishwa.')
        super().save(*a, **kw)

    def delete(self, *a, **kw):
        raise PermissionError('Logs za uhasibu haziwezi kufutwa.')
