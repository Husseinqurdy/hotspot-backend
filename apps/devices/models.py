import secrets

from django.db import models

from apps.clients.models import Client


def generate_device_api_key():
    """
    Tengeneza api_key ya kipekee kwa kila GSMDevice. Hii inachukua
    nafasi ya settings.DEVICE_API_KEY ya zamani (key MOJA ya pamoja
    kwa devices ZOTE) — sasa kila kifaa kina siri yake, hivyo kifaa
    cha account A hakiwezi kuiga account B.
    """
    return secrets.token_hex(24)  # 48-char hex string


class GSMDevice(models.Model):
    NETWORK_CHOICES = [
        ('vodacom', 'Vodacom M-Pesa'),
        ('tigo', 'Tigo Pesa'),
        ('airtel', 'Airtel Money'),
        ('halo', 'HaloPesa'),
    ]

    STATUS_UNCLAIMED = 'unclaimed'
    STATUS_ACTIVE = 'active'
    STATUS_CHOICES = [
        (STATUS_UNCLAIMED, 'Haijawekewa client (inasubiri admin)'),
        (STATUS_ACTIVE, 'Active'),
    ]

    # MUHIMU: hii ndiyo hali ya PROVISIONING (zero-touch), TOFAUTI na
    # is_active (ambayo ni admin enable/disable toggle ya kawaida,
    # chini kidogo). Kifaa kinapojitangaza kwa mara ya kwanza kupitia
    # /devices/checkin/, GSMDevice mpya inaundwa hapa na status
    # 'unclaimed' — client=None. Inabaki hivyo mpaka superadmin
    # a-claim kifaa (angalia claim() method chini).
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNCLAIMED)

    # null=True KWA MAKUSUDI: kifaa kipya (unclaimed) hakina mmiliki
    # bado — hii ndiyo tofauti kubwa na muundo wa awali ambao
    # ulidhani admin anaunda rekodi KABLA kifaa hakijawahi kuonekana.
    # Sasa ni kinyume: kifaa kinajitangaza kwanza, client anaongezwa
    # baadaye na superadmin (angalia claim()).
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='gsm_devices',
        null=True, blank=True,
        help_text="Mmiliki mkuu wa kifaa hiki. Tupu = bado hakijawekewa client (unclaimed).",
    )

    # Clients wengine (kwa hiari) wanaoruhusiwa kutumia lipa namba hii
    # hii — angalia eligible_clients() chini.
    shared_with = models.ManyToManyField(
        Client,
        related_name='shared_gsm_devices',
        blank=True,
        help_text="Clients wengine (kwa hiari) wanaoruhusiwa kutumia lipa namba hii hii.",
    )

    name = models.CharField(max_length=100, blank=True, default='')

    # blank/null=True: haijulikani mpaka kifaa kiwe claimed.
    network = models.CharField(max_length=20, choices=NETWORK_CHOICES, blank=True, null=True)
    lipa_number = models.CharField(max_length=20, blank=True, default='')
    phone_number = models.CharField(max_length=20, blank=True, default='')

    # device_id sasa ni "factory_id" — kifaa CHENYEWE kinajitambulisha
    # nayo (kwa mfano ESP.getEfuseMac() ya ESP32 — chip ID ya
    # kiwandani, ya kipekee kabisa duniani), SIYO admin anayeiweka kwa
    # mkono kama ilivyokuwa awali. Bado ni unique KIMFUMO.
    device_id = models.CharField(max_length=50, unique=True)

    # null=True KWA MAKUSUDI: kifaa cha 'unclaimed' HAKINA api_key
    # kabisa — haipewi hadi kifaa ki-claimed (angalia save() chini).
    # Hii inazuia hatari ya usalama: endapo mtu angebahatisha/kuiga
    # checkin ya factory_id kabla kifaa halisi hakijadaiwa, asingeweza
    # kuvuna api_key yenye maana yoyote kwa sababu haipo bado.
    api_key = models.CharField(max_length=64, null=True, blank=True, unique=True, editable=False)

    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, help_text="Admin enable/disable toggle (tofauti na 'status' ya provisioning).")
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['client_id', 'network']
        constraints = [
            models.UniqueConstraint(
                fields=['client', 'network'],
                name='unique_network_per_client',
            ),
        ]

    def __str__(self):
        if self.client_id:
            return f"{self.client.business_name} | {self.name} ({self.get_network_display()}) - {self.lipa_number}"
        return f"[UNCLAIMED] {self.device_id}"

    def save(self, *args, **kwargs):
        # MUHIMU: hapa ndipo 'claim' ya kweli inatokea — iwe kupitia
        # claim() method chini, au kupitia Django admin ya kawaida
        # (superadmin akichagua client kwa mkono kwenye admin form kwa
        # vifaa vya zamani/legacy). Wakati wowote client inapowekwa na
        # api_key bado haipo, tunazalisha api_key na kuweka status
        # active kiotomatiki — njia zote mbili za ku-assign client
        # zinaishia na tabia moja sahihi.
        if self.client_id and not self.api_key:
            self.api_key = generate_device_api_key()
            self.status = self.STATUS_ACTIVE
        super().save(*args, **kwargs)

    def claim(self, client, name, network, lipa_number, phone_number='', shared_with=None):
        """
        Fanya kifaa hiki kuwa mali ya client husika. Baada ya hii,
        kifaa kitapata api_key yake kwenye checkin inayofuata.
        """
        self.client = client
        self.name = name
        self.network = network
        self.lipa_number = lipa_number
        self.phone_number = phone_number
        self.save()  # save() ndiyo inayozalisha api_key (angalia juu)
        if shared_with is not None:
            self.shared_with.set(shared_with)
        return self

    def regenerate_api_key(self):
        """Tumika endapo key imevuja — inabatilisha ya zamani papo hapo."""
        self.api_key = generate_device_api_key()
        self.save(update_fields=['api_key'])
        return self.api_key

    def eligible_clients(self):
        """
        Orodha ya clients WOTE wanaoruhusiwa kutumia lipa namba hii —
        mmiliki mkuu (self.client) pamoja na wale wa kwenye
        shared_with (endapo wapo). Kwa kifaa cha 'unclaimed'
        (client=None), hii inarudisha orodha TUPU.
        """
        if not self.client_id:
            return Client.objects.none()
        ids = [self.client_id] + list(self.shared_with.values_list('id', flat=True))
        return Client.objects.filter(id__in=ids)
