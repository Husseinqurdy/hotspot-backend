from django.db import models
from django.utils import timezone
from apps.routers.models import MikroTikRouter


class Advertiser(models.Model):
    """
    Biashara/mtu anayelipia kutangaza. Mfumo mzima wa ads unasimamiwa
    na superadmin pekee - HAKUNA tenant scoping ya Client hapa.
    """
    name = models.CharField(max_length=200)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Advertisement(models.Model):
    AD_TYPE_BANNER = 'banner'
    AD_TYPE_VIDEO = 'video'
    AD_TYPE_SPONSORED = 'sponsored_access'
    AD_TYPE_CHOICES = [
        (AD_TYPE_BANNER, 'Banner Image'),
        (AD_TYPE_VIDEO, 'Video (pre-roll)'),
        (AD_TYPE_SPONSORED, 'Sponsored Free Access'),
    ]

    advertiser = models.ForeignKey(Advertiser, on_delete=models.CASCADE, related_name='ads')

    title = models.CharField(max_length=200)
    ad_type = models.CharField(max_length=20, choices=AD_TYPE_CHOICES, default=AD_TYPE_BANNER)
    media_file = models.FileField(upload_to='ads/%Y/%m/', blank=True, null=True)
    click_url = models.URLField(blank=True)

    # --- Configurable na wewe (superadmin) - HAKUNA hardcode ---
    sponsored_minutes = models.IntegerField(
        default=15,
        help_text="Dakika za access mtumiaji atapata akitazama ad hii (ad_type=sponsored_access pekee)"
    )
    cooldown_hours = models.IntegerField(
        default=24,
        help_text="Baada ya masaa mangapi MAC ile ile inaweza kupata sponsored access tena"
    )
    max_daily_grants_per_router = models.IntegerField(
        default=0,
        help_text="Kikomo cha jumla cha sponsored grants kwa siku kwa router (0 = hakuna kikomo)"
    )
    mikrotik_profile = models.CharField(
        max_length=100,
        default='sponsored_free',
        help_text="Jina la hotspot user profile kwenye MikroTik itakayotumika kwa sponsored access "
                   "(profile hii LAZIMA iwepo tayari kwenye kila router unayolenga)"
    )
    # -------------------------------------------------

    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Routers za CLIENT YEYOTE unaweza kuchagua hapa - superadmin anaona zote.
    # Ikiwa haina router yoyote iliyowekwa -> inaonekana kwenye routers ZOTE
    # kwenye platform nzima (across clients wote).
    routers = models.ManyToManyField(MikroTikRouter, blank=True, related_name='ads')

    priority = models.IntegerField(default=1, help_text="Namba kubwa zaidi = kipaumbele zaidi")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', '-created_at']

    def __str__(self):
        return f"{self.title} [{self.get_ad_type_display()}] - {self.advertiser.name}"

    def is_currently_active(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date and self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True


class AdImpression(models.Model):
    """Kila router inaripoti hapa ilipoonyesha ad kwa mtumiaji."""
    ad = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='impressions')
    router = models.ForeignKey(MikroTikRouter, on_delete=models.CASCADE, related_name='ad_impressions')
    client_mac = models.CharField(max_length=17, blank=True, db_index=True)
    shown_at = models.DateTimeField(auto_now_add=True)
    clicked = models.BooleanField(default=False)
    clicked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-shown_at']
        indexes = [
            models.Index(fields=['ad', 'router', 'shown_at']),
        ]

    def __str__(self):
        return f"Impression: {self.ad.title} @ {self.router.name}"


class SponsoredAccessLog(models.Model):
    """Kumbukumbu ya kila mtu aliyepewa dakika za bure - ndiyo msingi wa cooldown check."""
    ad = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='sponsored_grants')
    router = models.ForeignKey(MikroTikRouter, on_delete=models.CASCADE, related_name='sponsored_grants')
    client_mac = models.CharField(max_length=17, db_index=True)
    minutes_granted = models.IntegerField()
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-granted_at']
        indexes = [
            models.Index(fields=['client_mac', 'router', 'ad', 'granted_at']),
        ]

    def __str__(self):
        return f"{self.client_mac} -> {self.minutes_granted}min @ {self.router.name}"

