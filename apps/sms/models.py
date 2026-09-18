from django.db import models


class OutgoingSMS(models.Model):
    STATUS_CHOICES = [('queued', 'Inasubiri'), ('taken', 'Imechukuliwa'), ('sent', 'Imetumwa'), ('failed', 'Imeshindwa')]

    # MPYA: kabla queue ilikuwa moja ya pamoja kwa mfumo mzima — kifaa
    # chochote kingeweza kuchukua SMS ya client yeyote. Sasa kila
    # ujumbe umefungwa kwa client wake, na OutgoingSMSView inachuja
    # kwa eligible_clients za kifaa kinachouliza (angalia
    # apps/sms/views.py).
    client = models.ForeignKey(
        'clients.Client', on_delete=models.CASCADE, null=True, blank=True,
        related_name='outgoing_sms'
    )

    phone = models.CharField(max_length=15)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    priority = models.IntegerField(default=0)
    retries = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
<<<<<<< HEAD

    class Meta:
        ordering = ['-priority', 'created_at']

    def __str__(self):
        return f"SMS → {self.phone} [{self.status}]"
=======
    class Meta: ordering = ['-priority','created_at']
    def __str__(self): return f"SMS → {self.phone} [{self.status}]"
>>>>>>> ce77eb29d3fbe067206773bcdacb85bba7fb4c3c
