from celery import shared_task
from django.utils import timezone
import logging
logger = logging.getLogger('netsafi')

@shared_task
def expire_old_vouchers():
    from .models import Voucher
    from apps.routers.mikrotik import get_mikrotik_connection
    expired = Voucher.objects.filter(status='active', expires_at__lt=timezone.now()).select_related('router')
    count = 0
    for v in expired:
        api = get_mikrotik_connection(v.router)
        if api: api.remove_hotspot_user(v.code); api.disconnect()
        v.status = 'expired'; v.save(update_fields=['status']); count += 1
    logger.info(f"Expired {count} vouchers")
