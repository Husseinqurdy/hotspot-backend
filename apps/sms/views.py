import re, hashlib, logging
from django.conf import settings
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

class ReceiveSMSView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        if request.headers.get('X-API-Key','') != settings.DEVICE_API_KEY:
            return Response({'error':'Unauthorized'}, status=401)
        phone = request.data.get('phone','').strip()
        message = request.data.get('message','').strip()
        device_id = request.data.get('device_id','').strip()
        network_hint = request.data.get('network','').strip()
        if not phone or not message:
            return Response({'error':'phone na message zinahitajika'}, status=400)
        if device_id:
            try:
                from apps.devices.models import GSMDevice
                d = GSMDevice.objects.get(device_id=device_id, is_active=True)
                d.last_seen = timezone.now(); d.save(update_fields=['last_seen'])
            except: pass
        network = network_hint if network_hint else detect_network(phone)
        from apps.sms.tasks import process_payment_sms
        process_payment_sms.apply(kwargs={'phone': phone, 'sms_text': message, 'network': network, 'device_id': device_id})
        return Response({'status':'received','network':network})

class OutgoingSMSView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        if request.GET.get('secret','') != settings.DEVICE_API_KEY:
            return Response({'error':'Unauthorized'}, status=401)
        from .models import OutgoingSMS
        sms_list = OutgoingSMS.objects.filter(status='queued').order_by('-priority','created_at')[:10]
        if not sms_list: return Response({'messages':[]})
        ids = [s.id for s in sms_list]
        OutgoingSMS.objects.filter(id__in=ids).update(status='taken')
        return Response({'messages':[{'id':s.id,'phone':s.phone,'message':s.message} for s in sms_list]})

class SMSSentView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        if request.data.get('secret','') != settings.DEVICE_API_KEY:
            return Response({'error':'Unauthorized'}, status=401)
        from .models import OutgoingSMS
        for result in request.data.get('results',[]):
            try:
                sms = OutgoingSMS.objects.get(id=result['id'])
                if result.get('success'): sms.status='sent'; sms.sent_at=timezone.now()
                else:
                    sms.retries += 1
                    sms.status = 'failed' if sms.retries >= 3 else 'queued'
                sms.save()
            except: pass
        return Response({'status':'ok'})