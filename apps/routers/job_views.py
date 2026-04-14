import random
import string
import logging
from django.utils import timezone
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .models import MikroTikJob

logger = logging.getLogger('netsafi')


def generate_voucher_code(length=8) -> str:
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=length))


class PendingJobsView(APIView):
    """
    MikroTik inauliza hapa kila dakika 1 kupitia VPN.
    GET /api/jobs/pending/?router_id=1&secret=KEY
    """
    permission_classes = [AllowAny]

    def get(self, request):
        secret = request.query_params.get('secret', '')
        if secret != settings.DEVICE_API_KEY:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        router_id = request.query_params.get('router_id')
        if not router_id:
            return Response({'error': 'router_id inahitajika'}, status=status.HTTP_400_BAD_REQUEST)

        jobs = MikroTikJob.objects.filter(
            router_id=router_id,
            status=MikroTikJob.STATUS_PENDING,
        ).select_related('package')[:5]

        if not jobs:
            return Response({'jobs': []})

        # Mark as processing
        job_ids = [j.id for j in jobs]
        MikroTikJob.objects.filter(id__in=job_ids).update(status=MikroTikJob.STATUS_PROCESSING)

        jobs_data = []
        for job in jobs:
            # Generate unique code
            from apps.vouchers.models import Voucher
            for _ in range(10):
                code = generate_voucher_code()
                if not Voucher.objects.filter(code=code).exists():
                    break

            job.voucher_code = code
            job.save(update_fields=['voucher_code'])

            jobs_data.append({
                'job_id': job.id,
                'action': job.action,
                'voucher_code': code,
                'profile': job.package.mikrotik_profile,
                'duration': f"{job.package.duration_minutes}m",
                'comment': f"NetSafi|{job.customer_phone}|TZS{job.payment.amount:.0f}",
            })

        logger.info(f"Router {router_id}: Jobs {len(jobs_data)} zimetumwa")
        return Response({'jobs': jobs_data})


class CompleteJobView(APIView):
    """
    MikroTik inaripoti baada ya kutekeleza kazi.
    POST /api/jobs/complete/
    """
    permission_classes = [AllowAny]

    def post(self, request):
        secret = request.data.get('secret', '')
        if secret != settings.DEVICE_API_KEY:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        job_id = request.data.get('job_id')
        success = request.data.get('success', False)
        error_msg = request.data.get('error', '')

        try:
            job = MikroTikJob.objects.select_related('payment', 'package', 'client').get(id=job_id)
        except MikroTikJob.DoesNotExist:
            return Response({'error': 'Job haikupatikana'}, status=status.HTTP_404_NOT_FOUND)

        if success:
            from apps.vouchers.models import Voucher
            from apps.payments.models import Payment

            # Hifadhi voucher
            Voucher.objects.create(
                client=job.client, router=job.router,
                package=job.package, payment=job.payment,
                code=job.voucher_code, customer_phone=job.customer_phone,
                status='active',
            )

            # Sasisha payment na bakaa
            job.payment.status = Payment.STATUS_COMPLETED
            job.payment.save(update_fields=['status'])
            job.client.balance += job.payment.client_share
            job.client.save(update_fields=['balance'])

            # Sasisha job
            job.status = MikroTikJob.STATUS_COMPLETED
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'completed_at'])

            # Tuma SMS ya voucher kupitia A7670E
            from apps.sms.tasks import queue_voucher_sms
            queue_voucher_sms.delay(
                phone=job.customer_phone,
                code=job.voucher_code,
                package_name=job.package.name,
                duration=job.package.duration_display(),
                speed=f"{job.package.speed_down}Mbps",
                payment_id=job.payment.id,
            )

            logger.info(f"✅ Job {job_id}: Voucher {job.voucher_code} → {job.customer_phone}")
            return Response({'status': 'completed', 'voucher': job.voucher_code})

        else:
            job.retries += 1
            if job.retries >= 3:
                job.status = MikroTikJob.STATUS_FAILED
                job.error_message = error_msg
                logger.error(f"❌ Job {job_id} imeshindwa mara 3: {error_msg}")
            else:
                job.status = MikroTikJob.STATUS_PENDING
                logger.warning(f"⚠️ Job {job_id} imeshindwa, itajaribu tena ({job.retries}/3)")
            job.save(update_fields=['status', 'retries', 'error_message'])
            return Response({'status': 'failed', 'retry': job.retries < 3})
