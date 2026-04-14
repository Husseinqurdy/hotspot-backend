import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotspot.settings')
app = Celery('hotspot')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'check-routers-every-5min': {
        'task': 'apps.routers.tasks.check_all_routers',
        'schedule': 300.0,
    },
    'expire-vouchers-every-hour': {
        'task': 'apps.vouchers.tasks.expire_old_vouchers',
        'schedule': 3600.0,
    },
    
    'retry-failed-jobs': {
        'task': 'apps.routers.tasks.retry_failed_jobs', 'schedule': 120.0,
        
        },
}
