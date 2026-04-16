from django.db import models
class OutgoingSMS(models.Model):
    STATUS_CHOICES = [('queued','Inasubiri'),('taken','Imechukuliwa'),('sent','Imetumwa'),('failed','Imeshindwa')]
    phone = models.CharField(max_length=15)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    priority = models.IntegerField(default=0)
    retries = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    class Meta: ordering = ['-priority','created_at']
    def __str__(self): return f"SMS → {self.phone} [{self.status}]"
