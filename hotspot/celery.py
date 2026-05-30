import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv('/root/hotspot-backend/.env')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotspot.settings')

app = Celery('hotspot')

app.config_from_object(
    'django.conf:settings',
    namespace='CELERY'
)

redis_url = os.environ.get(
    'REDIS_URL',
    'redis://localhost:6379/0'
)

app.conf.broker_url = redis_url
app.conf.result_backend = redis_url

app.autodiscover_tasks()

import apps.sms.tasks
import apps.routers.tasks
import apps.vouchers.tasks

app.conf.beat_schedule = {

    'check-routers-every-5min': {
        'task': 'apps.routers.tasks.check_all_routers',
        'schedule': 300.0,
    },

    'process-pending-jobs-every-20sec': {
        'task': 'apps.routers.tasks.process_pending_jobs',
        'schedule': 20.0,
    },

    'retry-failed-jobs': {
        'task': 'apps.routers.tasks.retry_failed_jobs',
        'schedule': 120.0,
    },

    'expire-vouchers-every-hour': {
        'task': 'apps.vouchers.tasks.expire_old_vouchers',
        'schedule': 3600.0,
    },
}