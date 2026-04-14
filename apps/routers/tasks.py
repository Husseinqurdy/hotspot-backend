import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('netsafi')

@shared_task
def check_all_routers():
    from .models import MikroTikRouter
    from .mikrotik import get_mikrotik_connection
    routers = MikroTikRouter.objects.all()
    online = 0
    for r in routers:
        api = get_mikrotik_connection(r)
        alive = api.is_alive() if api else False
        if api: api.disconnect()
        r.is_online = alive
        if alive: r.last_seen = timezone.now(); online += 1
        r.save(update_fields=['is_online','last_seen'])
    logger.info(f"Router check: {online}/{routers.count()} online")

@shared_task
def retry_failed_jobs():
    """Jaribu tena jobs zilizoshindwa kama router iko online."""
    from .models import MikroTikJob
    failed = MikroTikJob.objects.filter(status='failed', retries__lt=3).select_related('router')
    count = 0
    for job in failed:
        if job.router.is_online:
            job.status = MikroTikJob.STATUS_PENDING
            job.save(update_fields=['status'])
            count += 1
    if count: logger.info(f"Jobs {count} zimewekwa tena kujaribu")
