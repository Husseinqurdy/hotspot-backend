import re
import hashlib
import logging
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

logger = logging.getLogger('netsafi')


def detect_network(phone: str) -> str:
    phone = phone.strip()
    if phone.startswith('+255'): phone = '0' + phone[4:]
    elif phone.startswith('255'): phone = '0' + phone[3:]
    prefix = phone[:3] if len(phone) >= 3 else ''
    if prefix in ['074','075','076']: return 'vodacom'
    elif prefix in ['065','067','071']: return 'tigo'
    elif prefix in ['068','069','078']: return 'airtel'
    elif prefix in ['062']: return 'halo'
    return 'unknown'


class ReceiveSMSView(APIView):
    """
    A7670E inatuma SMS zilizoingia hapa.
    POST /api/sms/receive/
    Headers: X-API-Key: <device_api_key>
    Body: {"phone":"255744...","message":"TZS 500...","device_id":"VODA_001","network":"vodacom"}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        api_key = request.headers.get('X-API-Key', '')
        if api_key != settings.DEVICE_API_KEY:
            logger.warning(f"Invalid API key from {request.META.get('REMOTE_ADDR')}")
            return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        phone = request.data.get('phone', '').strip()
        message = request.data.get('message', '').strip()
        device_id = request.data.get('device_id', '').strip()
        network_hint = request.data.get('network', '').strip()

        if not phone or not message:
            return Response({'error': 'phone na message zinahitajika'}, status=status.HTTP_400_BAD_REQUEST)

        # Sasisha last_seen ya device
        if device_id:
            try:
                from apps.devices.models import GSMDevice
                device = GSMDevice.objects.get(device_id=device_id, is_active=True)
                device.last_seen = timezone.now()
                device.save(update_fields=['last_seen'])
            except Exception:
                pass

        network = network_hint if network_hint else detect_network(phone)
        logger.info(f"SMS received | Device: {device_id} | Phone: {phone} | Network: {network}")

        from apps.sms.tasks import process_payment_sms
        process_payment_sms.delay(phone=phone, sms_text=message, network=network, device_id=device_id)

        return Response({'status': 'received', 'network': network})


class OutgoingSMSView(APIView):
    """
    A7670E inachukua SMS zinazongoja kutumwa.
    GET /api/sms/outgoing/?secret=KEY&device_id=VODA_001
    """
    permission_classes = [AllowAny]

    def get(self, request):
        secret = request.query_params.get('secret', '')
        if secret != settings.DEVICE_API_KEY:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        from apps.sms.models import OutgoingSMS
        sms_list = OutgoingSMS.objects.filter(
            status=OutgoingSMS.STATUS_QUEUED
        ).order_by('-priority', 'created_at')[:10]

        if not sms_list:
            return Response({'messages': []})

        ids = [s.id for s in sms_list]
        OutgoingSMS.objects.filter(id__in=ids).update(status=OutgoingSMS.STATUS_TAKEN)

        return Response({
            'messages': [{'id': s.id, 'phone': s.phone, 'message': s.message} for s in sms_list]
        })


class SMSSentView(APIView):
    """
    A7670E inaripoti SMS zilizotumwa.
    POST /api/sms/sent/
    Body: {"secret":"KEY","results":[{"id":1,"success":true},{"id":2,"success":false,"error":"..."}]}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        secret = request.data.get('secret', '')
        if secret != settings.DEVICE_API_KEY:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        from apps.sms.models import OutgoingSMS
        results = request.data.get('results', [])

        for result in results:
            try:
                sms = OutgoingSMS.objects.get(id=result['id'])
                if result.get('success'):
                    sms.status = OutgoingSMS.STATUS_SENT
                    sms.sent_at = timezone.now()
                else:
                    sms.retries += 1
                    sms.status = OutgoingSMS.STATUS_FAILED if sms.retries >= 3 else OutgoingSMS.STATUS_QUEUED
                sms.save()
            except Exception as e:
                logger.error(f"SMS update failed: {e}")

        return Response({'status': 'ok'})
