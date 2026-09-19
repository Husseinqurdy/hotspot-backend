import random, logging
from django.utils import timezone
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import MikroTikJob

logger = logging.getLogger('netsafi')

def generate_voucher_code(length=8):
    return ''.join(random.choices('ABCDEFGHJKMNPQRSTUVWXYZ23456789', k=length))

class PendingJobsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        secret = request.query_params.get('secret', '')
        if secret != settings.DEVICE_API_KEY:
            return Response({'error':'Unauthorized'}, status=401)
        router_id = request.query_params.get('router_id')
        if not router_id:
            return Response({'error':'router_id inahitajika'}, status=400)
        jobs = MikroTikJob.objects.filter(router_id=router_id, status=MikroTikJob.STATUS_PENDING).select_related('package')[:5]
        if not jobs: return Response({'jobs':[]})
        job_ids = [j.id for j in jobs]
        MikroTikJob.objects.filter(id__in=job_ids).update(status=MikroTikJob.STATUS_PROCESSING)
        jobs_data = []
        for job in jobs:
            # Heshimu voucher_code iliyowekwa tayari na process_payment_sms —
            # client mwenye routers kadhaa anapata jobs kadhaa (moja kwa kila
            # router) zenye code MOJA ya pamoja. Kuizalisha upya hapa
            # kungevunja mfumo huo (kila router ingepata code tofauti).
            code = job.voucher_code
            if not code:
                from apps.vouchers.models import Voucher
                for _ in range(10):
                    code = generate_voucher_code()
                    if not Voucher.objects.filter(code=code).exists(): break
                job.voucher_code = code
                job.save(update_fields=['voucher_code'])
            jobs_data.append({'job_id':job.id,'action':job.action,'voucher_code':code,'profile':job.package.mikrotik_profile,'duration':f"{job.package.duration_minutes}m",'comment':f"NetSafi|{job.customer_phone}|TZS{job.payment.amount:.0f}"})
        logger.info(f"Router {router_id}: Jobs {len(jobs_data)} zimetumwa")
        return Response({'jobs':jobs_data})

class CompleteJobView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        secret = request.data.get('secret','')
        if secret != settings.DEVICE_API_KEY:
            return Response({'error':'Unauthorized'}, status=401)
        job_id = request.data.get('job_id')
        success = request.data.get('success', False)
        error_msg = request.data.get('error','')
        try:
            job = MikroTikJob.objects.select_related('payment','package','client','router').get(id=job_id)
        except MikroTikJob.DoesNotExist:
            return Response({'error':'Job haikupatikana'}, status=404)
        if success:
            from apps.vouchers.models import Voucher, VoucherRouterPresence
            from apps.payments.models import Payment

            # get_or_create: job ya KWANZA kwa code hii ndiyo inayounda
            # Voucher; routers zingine (jobs za malipo yale yale) zinapata
            # Voucher ile ile bila kujaribu kuiunda upya — kwa vile
            # Voucher.code ina unique=True, kuunda mara mbili kwa code
            # moja kungesababisha IntegrityError.
            voucher, voucher_created = Voucher.objects.get_or_create(
                code=job.voucher_code,
                defaults={
                    'client': job.client,
                    'router': job.router,
                    'package': job.package,
                    'payment': job.payment,
                    'customer_phone': job.customer_phone,
                    'status': 'active',
                }
            )

            # Presence ya voucher hii kwenye ROUTER HII mahususi.
            VoucherRouterPresence.objects.get_or_create(
                voucher=voucher,
                router=job.router,
                defaults={'status': VoucherRouterPresence.STATUS_ACTIVE},
            )

            if job.payment and job.payment.status != Payment.STATUS_COMPLETED:
                job.payment.status = Payment.STATUS_COMPLETED
                job.payment.save(update_fields=['status'])

            # MUHIMU: balance ya client TAYARI imeongezwa mara MOJA
            # wakati Payment ilipoundwa (apps.sms.tasks.process_payment_sms).
            # Kuongeza tena hapa (kama ilivyokuwa awali) kungesababisha
            # client kupata balance mara kadhaa kwa malipo MOJA — hasa
            # sasa kwamba client mwenye routers kadhaa anapata jobs
            # kadhaa kwa malipo yale yale. Kwa hiyo SIYO tunaiongeza hapa.

            job.status = MikroTikJob.STATUS_COMPLETED
            job.completed_at = timezone.now()
            job.save(update_fields=['status','completed_at'])

            # Tuma SMS ya voucher MARA MOJA TU — job ya kwanza
            # iliyounda Voucher (voucher_created=True). Zinazofuata
            # (routers zingine za malipo yale yale) hazitumi SMS
            # nyingine ili mteja asipokee ujumbe unaofanana mara kadhaa.
            if voucher_created:
                from apps.sms.tasks import queue_voucher_sms
                queue_voucher_sms.delay(phone=job.customer_phone, code=job.voucher_code, package_name=job.package.name, duration=job.package.duration_display(), speed=f"{job.package.speed_down}Mbps", payment_id=job.payment.id if job.payment else None)

            logger.info(f"✅ Job {job_id}: Voucher {job.voucher_code} → {job.customer_phone} (mpya: {voucher_created})")
            return Response({'status':'completed','voucher':job.voucher_code})
        else:
            job.retries += 1
            if job.retries >= 3:
                job.status = MikroTikJob.STATUS_FAILED
                job.error_message = error_msg
            else:
                job.status = MikroTikJob.STATUS_PENDING
            job.save(update_fields=['status','retries','error_message'])
            return Response({'status':'failed','retry':job.retries<3})

