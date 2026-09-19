import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.clients.models import Client
from apps.routers.models import MikroTikRouter
from apps.packages.models import Package
from apps.payments.models import Payment


class VoucherPrintBatch(models.Model):
    """
    Kikundi cha vocha zilizoundwa kwa mara moja (single au batch),
    pamoja na PDF moja inayoweza kuchapishwa tena au kufutwa.

    Hii ndiyo "historia ya vocha" inayoonekana kwenye Analysis page —
    imehifadhiwa kwa profile name na tarehe iliyoundwa.
    """
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='print_batches')
    router = models.ForeignKey(MikroTikRouter, on_delete=models.SET_NULL, null=True, blank=True)
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True)

    # Snapshot — hata kama profile/package ikifutwa au kubadilishwa baadaye,
    # historia inabaki sahihi kama ilivyokuwa wakati wa kuundwa.
    profile_name = models.CharField(max_length=100)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    quantity = models.PositiveIntegerField(default=1)
    theme = models.CharField(max_length=20, default='blue')

    pdf_file = models.FileField(upload_to='voucher_pdfs/%Y/%m/', null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voucher_print_batches',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.profile_name} x{self.quantity} — {self.created_at.strftime('%Y-%m-%d')}"


class Voucher(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('used', 'Imetumika'), ('expired', 'Imeisha')]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='vouchers')
    router = models.ForeignKey(MikroTikRouter, on_delete=models.CASCADE)
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, null=True, blank=True)

    # Kikundi cha PDF kilichozalisha voucher hii (null kwa vouchers za zamani
    # zilizoundwa kabla ya feature hii, au vouchers zisizo na PDF).
    print_batch = models.ForeignKey(
        VoucherPrintBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vouchers',
    )

    code = models.CharField(max_length=20, unique=True, db_index=True)
    customer_phone = models.CharField(max_length=15, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Snapshot ya bei wakati voucher ilipoundwa — muhimu kwa ripoti sahihi
    # hata kama bei ya package itabadilika baadaye.
    sold_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)  # ← inajazwa na Celery poll task
    expires_at = models.DateTimeField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)

    # Epuka kutuma notification ya "voucher imetumika" mara mbili kwa voucher moja
    usage_notified = models.BooleanField(default=False)
    sync_missing_since = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.sold_price and self.package_id:
            self.sold_price = self.package.price
        # MUHIMU: expires_at HAIWEKWI hapa kabisa — inabaki None mpaka
        # voucher itumike kwa mara ya kwanza (used_at kuwekwa na
        # check_voucher_usage / sync_voucher_status_from_mikrotik, ambazo
        # zote sasa zinaweka expires_at = used_at + duration wakati huo huo).
        #
        # SABABU: ile default ya awali (created_at + 2×duration) haikuwa
        # na faida yoyote — expire_old_vouchers tayari ina sharti la
        # `used_at__isnull=False`, kwa hiyo voucher isiyotumika kamwe
        # haiwezi kufutwa na task hiyo hata bila default hii. Default hiyo
        # ilikuwa ikisababisha MADHARA TU: voucher iliyoundwa (mfano batch)
        # lakini ikatumika siku kadhaa baadaye ilikuwa na expires_at
        # iliyokwisha pita KABLA hata haijaanza kutumika — na hivyo
        # kufutwa mapema sana. Kuiondoa hapa kunazuia darasa lote la
        # hitilafu hii, badala ya kutegemea kila task 'ikumbuke'
        # kuisahihisha.
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} | {self.status}"


class VoucherRouterPresence(models.Model):
    """
    Client mwenye routers zaidi ya moja: voucher MOJA (rekodi moja ya
    mauzo, `Voucher` hapo juu) inaundwa kama hotspot user kwenye ROUTERS
    ZOTE za client wakati wa malipo — kwa sababu hatujui mapema mteja
    ataingia kwenye router gani. Rekodi hii inashikilia "nakala" moja ya
    voucher kwenye router moja.

    Wakati mteja anapoingiza voucher kwenye router mojawapo (kugundulika
    na `sync_voucher_status_from_mikrotik`), presence za routers zingine
    zote zinafutwa moja kwa moja kwenye MikroTik na kuwekwa status='removed'
    — hii inazuia voucher hiyo hiyo kutumika mara mbili kwenye routers
    tofauti, na kusafisha hotspot users zisizo za lazima.
    """
    STATUS_ACTIVE = 'active'
    STATUS_REMOVED = 'removed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active — ipo kwenye router, bado haijafutwa'),
        (STATUS_REMOVED, 'Imeondolewa — voucher ilitumika router nyingine'),
        (STATUS_FAILED, 'Imeshindwa kuundwa kwenye router hii'),
    ]

    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='presences')
    router = models.ForeignKey(MikroTikRouter, on_delete=models.CASCADE, related_name='voucher_presences')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ['voucher', 'router']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.voucher.code} @ {self.router.name} ({self.status})"


class DailySalesReport(models.Model):
    """
    Ripoti ya mauzo ya kila siku — inaundwa na Celery Beat saa 23:30 kila
    usiku, ikitumia Voucher.sold_price na vouchers zilizo na used_at ya
    siku hiyo (yaani zilizoingia kwenye scheduler ya MikroTik = mteja
    ameshaitumia).

    MUHIMU: hii inahesabu kwa `Voucher` (rekodi MOJA kwa kila mauzo),
    SIYO kwa `VoucherRouterPresence` — hivyo hata client mwenye routers
    kadhaa, mauzo hayahesabiwi mara mbili kwa sababu ya presence nyingi.
    """
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='sales_reports')
    date = models.DateField()
    total_vouchers_sold = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Mfano: [{"package": "Saa 1", "count": 12, "subtotal": 6000}, ...]
    breakdown = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        unique_together = ['client', 'date']

    def __str__(self):
        return f"{self.client.business_name} — {self.date} — TZS {self.total_revenue}"

