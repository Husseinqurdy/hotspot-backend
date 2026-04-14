from django.db import models

class SMSLog(models.Model):
    """Rekodi ya SMS zilizotumwa."""
    STATUS_CHOICES = [('queued','Inasubiri'),('sent','Imetumwa'),('failed','Imeshindwa')]
    phone_number = models.CharField(max_length=15)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    class Meta: ordering = ['-created_at']
    def __str__(self): return f"{self.phone_number} | {self.status}"

class OutgoingSMS(models.Model):
    """
    SMS zinazosubiri kutumwa na A7670E device.
    A7670 inachukua SMS hizi na kuzituma yenyewe.
    """
    STATUS_QUEUED = 'queued'
    STATUS_TAKEN = 'taken'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [(STATUS_QUEUED,'Inasubiri'),(STATUS_TAKEN,'Imechukuliwa'),(STATUS_SENT,'Imetumwa'),(STATUS_FAILED,'Imeshindwa')]

    phone = models.CharField(max_length=15)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    priority = models.IntegerField(default=0, help_text='Juu = muhimu zaidi')
    retries = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-priority', 'created_at']
    def __str__(self): return f"SMS → {self.phone} [{self.status}]"
