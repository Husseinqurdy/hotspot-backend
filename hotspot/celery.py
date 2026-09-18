import os
from celery import Celery
<<<<<<< HEAD
from celery.schedules import crontab
=======
>>>>>>> ce77eb29d3fbe067206773bcdacb85bba7fb4c3c
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

<<<<<<< HEAD
    # ── MPYA: oanisha hali ya vouchers za MALIPO (Payment) na schedulers
    #    za MikroTik kila dakika 1 — hii ndiyo inayogundua voucher
    #    imetumika kwenye router gani, na kufuta 'nakala' zake kwenye
    #    routers zingine za client mwenye routers kadhaa. HAIKUWA
    #    imeorodheshwa hapa awali — bila hii, mfumo mzima wa 'presence
    #    kwenye routers kadhaa + auto-delete' hauwezi kufanya kazi. ──
    'sync-voucher-status-every-1min': {
        'task': 'apps.routers.tasks.sync_voucher_status_from_mikrotik',
        'schedule': 60.0,
    },

=======
>>>>>>> ce77eb29d3fbe067206773bcdacb85bba7fb4c3c
    'expire-vouchers-every-hour': {
        'task': 'apps.vouchers.tasks.expire_old_vouchers',
        'schedule': 3600.0,
    },
<<<<<<< HEAD

    # ── MPYA: tambua vouchers zilizotumika (ziliingia kwenye scheduler
    #    ya MikroTik) kila dakika 3, kisha tuma notification papo hapo ──
    'check-voucher-usage-every-3min': {
        'task': 'apps.vouchers.tasks.check_voucher_usage',
        'schedule': 180.0,
    },

    # ── MPYA: ripoti ya mauzo ya siku, saa 23:30 kila usiku ──
    'daily-sales-report-2330': {
        'task': 'apps.vouchers.tasks.generate_daily_sales_report',
        'schedule': crontab(hour=23, minute=30),
    },
}

=======
}
>>>>>>> ce77eb29d3fbe067206773bcdacb85bba7fb4c3c
