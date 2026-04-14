from django.db import models
from apps.clients.models import Client

class Package(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='packages')
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
        unique_together = ['client','price']
    def __str__(self): return f"{self.name} - TZS {self.price}"
    def duration_display(self):
        if self.duration_minutes < 60: return f"Dakika {self.duration_minutes} / {self.duration_minutes} Minutes"
        elif self.duration_minutes < 1440: h = self.duration_minutes//60; return f"Saa {h} / {h} Hours"
        d = self.duration_minutes//1440; return f"Siku {d} / {d} Days"
