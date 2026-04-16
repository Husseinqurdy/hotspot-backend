from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_SUPERADMIN = 'superadmin'
    ROLE_CLIENT = 'client'
    ROLE_CHOICES = [(ROLE_SUPERADMIN,'Super Admin'),(ROLE_CLIENT,'Client')]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CLIENT)
    phone = models.CharField(max_length=15, blank=True)
    is_active = models.BooleanField(default=True)
    def is_superadmin(self): return self.role == self.ROLE_SUPERADMIN
    def is_client(self): return self.role == self.ROLE_CLIENT
    def __str__(self): return f"{self.username} ({self.role})"
