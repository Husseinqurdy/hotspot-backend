import random
import string
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('hotspot')


def generate_voucher_code():
    """Tengeneza code ya nasibu ya herufi 8."""
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=8))


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
        r.save(update_fields=['is_online', 'last_seen'])
    logger.info(f"Router check: {online}/{routers.count()} online")


@shared_task
def retry_failed_jobs():
    from .models import MikroTikJob
    failed = MikroTikJob.objects.filter(
        status='failed', retries__lt=3
    ).select_related('router')
    count = 0
    for job in failed:
        if job.router.is_online:
            job.status = MikroTikJob.STATUS_PENDING
            job.save(update_fields=['status'])
            count += 1
    if count:
        logger.info(f"Jobs {count} zimewekwa tena")


@shared_task
def process_pending_jobs():
    """
    Tekeleza MikroTik jobs zote zilizo pending.
    Inaitwa na Celery Beat kila dakika 1.
    """
    from .models import MikroTikJob
    from .mikrotik import get_mikrotik_connection
    from apps.vouchers.models import Voucher
    from apps.payments.models import Payment
    from apps.sms.tasks import queue_voucher_sms

    jobs = MikroTikJob.objects.filter(
        status=MikroTikJob.STATUS_PENDING
    ).select_related('router', 'package', 'client', 'payment')[:20]

    if not jobs:
        return

    logger.info(f"Processing {jobs.count()} pending jobs...")

    for job in jobs:
        try:
            # Weka status processing
            job.status = MikroTikJob.STATUS_PROCESSING
            job.save(update_fields=['status'])

            # Unganika MikroTik
            api = get_mikrotik_connection(job.router)
            if not api:
                logger.error(f"Job {job.id}: Router {job.router.name} haipo online")
                job.status = MikroTikJob.STATUS_FAILED
                job.error_message = "Router haipo online"
                job.retries += 1
                job.save(update_fields=['status', 'error_message', 'retries'])
                continue

            # Tengeneza voucher code
            code = generate_voucher_code()

            # Hakikisha code haipo tayari kwenye MikroTik
            for _ in range(5):
                existing = api.command(
                    '/ip/hotspot/user/print',
                    queries={'name': code}
                )
                if not existing:
                    break
                code = generate_voucher_code()

            # Unda hotspot user kwenye MikroTik
            profile = job.package.mikrotik_profile or 'default'
            comment = f"NetSafi|{job.client.business_name}|{job.customer_phone}"

            success = api.add_hotspot_user(
                username=code,
                password=code,
                profile=profile,
                comment=comment
            )

            api.disconnect()

            if not success:
                raise Exception("add_hotspot_user ilishindwa")

            # Hifadhi voucher kwenye database
            voucher = Voucher.objects.create(
                client=job.client,
                router=job.router,
                package=job.package,
                payment=job.payment,
                code=code,
                customer_phone=job.customer_phone,
                status='active',
            )

            # Weka job completed
            job.status = MikroTikJob.STATUS_COMPLETED
            job.voucher_code = code
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'voucher_code', 'completed_at'])

            # Weka payment completed
            if job.payment:
                job.payment.status = Payment.STATUS_COMPLETED
                job.payment.processed_at = timezone.now()
                job.payment.save(update_fields=['status', 'processed_at'])

            # Tuma SMS ya voucher kwa mteja
            queue_voucher_sms.delay(
                phone=job.customer_phone,
                code=code,
                package_name=job.package.name,
                duration=job.package.duration_display(),
                speed=f"{job.package.speed_down}Mbps/{job.package.speed_up}Mbps",
                payment_id=job.payment.id if job.payment else None,
            )

            logger.info(
                f"✅ Job {job.id} completed — "
                f"Code: {code} | "
                f"Client: {job.client.business_name} | "
                f"Package: {job.package.name} | "
                f"Phone: {job.customer_phone}"
            )

        except Exception as e:
            logger.error(f"❌ Job {job.id} failed: {e}")
            job.status = MikroTikJob.STATUS_FAILED
            job.error_message = str(e)
            job.retries += 1
            job.save(update_fields=['status', 'error_message', 'retries'])

            # Tuma SMS ya hitilafu kwa mteja
            try:
                from apps.sms.tasks import queue_sms
                queue_sms(
                    job.customer_phone,
                    "Samahani, kulikuwa na hitilafu. "
                    "Tutajaribu tena hivi karibuni.\n"
                    "Sorry, there was an error. We will retry shortly.",
                    priority=5
                )
            except:
                pass