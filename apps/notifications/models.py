from django.db import models
from apps.clients.models import Client


class Notification(models.Model):
    LEVEL_CHOICES = [
        ('info', 'Taarifa'),
        ('success', 'Mafanikio'),
        ('warning', 'Onyo'),
        ('error', 'Hitilafu'),
    ]

    # Ikiwa client=None, notification hii ni ya super admin pekee (mfumo mzima).
    # Ikiwa client imewekwa, notification hii inaonekana kwa client huyo tu.
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )

    title = models.CharField(max_length=150)
    message = models.TextField()
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')

    # Kiungo cha hiari — mfano '/client/analysis' ili notification ibonyezwe
    # na kupeleka mtumiaji moja kwa moja kwenye ukurasa husika.
    link = models.CharField(max_length=200, blank=True)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        target = self.client.business_name if self.client_id else 'Admin'
        return f"[{target}] {self.title}"

