import re, hashlib, logging
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
logger = logging.getLogger('netsafi')


def detect_network(phone):
    phone = phone.strip()
    if phone.startswith('+255'): phone = '0' + phone[4:]
    elif phone.startswith('255'): phone = '0' + phone[3:]
    prefix = phone[:3] if len(phone) >= 3 else ''
    if prefix in ['074','075','076']: return 'vodacom'
    elif prefix in ['065','067','071']: return 'tigo'
    elif prefix in ['068','069','078']: return 'airtel'
    elif prefix in ['062']: return 'halo'
    return 'unknown'


def _authenticate_device(request):
    """
    MPYA: badala ya kulinganisha na settings.DEVICE_API_KEY (key MOJA
    ya pamoja kwa devices ZOTE), sasa kila request lazima ilete
    device_id + api_key inayolingana na GSMDevice husika.
    """
    from apps.devices.models import GSMDevice

    device_id = request.data.get('device_id', '').strip()
    api_key = request.headers.get('X-API-Key', '') or request.data.get('secret', '')

    if not device_id or not api_key:
        return None, Response({'error': 'device_id na api_key zinahitajika'}, status=401)

    try:
        device = GSMDevice.objects.select_related('client').prefetch_related('shared_with').get(
            device_id=device_id, api_key=api_key, is_active=True
        )
    except GSMDevice.DoesNotExist:
        logger.warning(f"Auth imeshindwa kwa device_id={device_id}")
        return None, Response({'error': 'Unauthorized'}, status=401)

    return device, None


class ReceiveSMSView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        device, error = _authenticate_device(request)
        if error:
            return error

        phone = request.data.get('phone', '').strip()
        message = request.data.get('message', '').strip()
        network_hint = request.data.get('network', '').strip()

        if not phone or not message:
            return Response({'error': 'phone na message zinahitajika'}, status=400)

        device.last_seen = timezone.now()
        device.save(update_fields=['last_seen'])

        network = network_hint if network_hint else detect_network(phone)

        from apps.sms.tasks import process_payment_sms
        process_payment_sms.apply(kwargs={
            'phone': phone,
            'sms_text': message,
            'network': network,
            'device_id': device.device_id,
        })
        return Response({'status': 'received', 'network': network})


class OutgoingSMSView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        device, error = _authenticate_device(request)
        if error:
            return error

        from .models import OutgoingSMS
        # MPYA: kifaa kinapata ujumbe wa client YEYOTE aliye kwenye
        # eligible_clients yake — kwa kifaa cha kawaida hii ni client
        # mmoja tu (mmiliki); kwa kifaa kinachoshirikiwa, ni mmiliki +
        # walioongezwa kwenye shared_with.
        eligible_client_ids = [c.id for c in device.eligible_clients()]
        sms_list = OutgoingSMS.objects.filter(
            status='queued', client_id__in=eligible_client_ids
        ).order_by('-priority', 'created_at')[:10]

        if not sms_list:
            return Response({'messages': []})

        ids = [s.id for s in sms_list]
        OutgoingSMS.objects.filter(id__in=ids).update(status='taken')
        return Response({'messages': [{'id': s.id, 'phone': s.phone, 'message': s.message} for s in sms_list]})


class SMSSentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        device, error = _authenticate_device(request)
        if error:
            return error

        from .models import OutgoingSMS
        eligible_client_ids = [c.id for c in device.eligible_clients()]
        for result in request.data.get('results', []):
            try:
                # MUHIMU: hakikisha SMS hii ilitoka kwa client mmoja
                # kati ya eligible_clients za kifaa hiki hiki.
                sms = OutgoingSMS.objects.get(id=result['id'], client_id__in=eligible_client_ids)
                if result.get('success'):
                    sms.status = 'sent'
                    sms.sent_at = timezone.now()
                else:
                    sms.retries += 1
                    sms.status = 'failed' if sms.retries >= 3 else 'queued'
                sms.save()
            except OutgoingSMS.DoesNotExist:
                pass
        return Response({'status': 'ok'})
