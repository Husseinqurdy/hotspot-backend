import re, hashlib, logging
from celery import shared_task
logger = logging.getLogger('netsafi')

def parse_payment_sms(sms_text):
    PATTERNS = [
        r'TZS\s*([\d,]+\.?\d*)\s+paid\s+to\s+\w+\s+Ref\s+(\w+)',
        r'Confirmed\.\s*TZS\s*([\d,]+)\s+sent.*?Ref[:\s]+(\w+)',
        r'Umelipa\s+TZS\s+([\d,]+)\s+kwa\s+\w+[.\s]+Kumbukumbu\s+namba\s+(\w+)',
        r'Confirmed\.\s+TZS([\d,]+)\s+sent\s+to[\w\s]+Ref[:\s]+(\w+)',
        r'Malipo\s+ya\s+TZS\s+([\d,]+)\s+yamefanikiwa.*?kumbukumbu[:\s]+(\w+)',
        r'(?:TZS|Tsh)[.\s]*([\d,]+).*?(?:Ref|ref|REF|kumbukumbu)[:\s]+(\w{4,})',
    ]
    for pattern in PATTERNS:
        m = re.search(pattern, sms_text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                amount = float(m.group(1).replace(',',''))
                ref = m.group(2).upper().strip()
                if amount > 0 and len(ref) >= 4: return {'amount':amount,'reference':ref}
            except: continue
    return None

def queue_sms(phone, message, priority=0):
    from apps.sms.models import OutgoingSMS
    OutgoingSMS.objects.create(phone=phone, message=message, priority=priority)

@shared_task(bind=True, max_retries=2)
def process_payment_sms(self, phone, sms_text, network='unknown', device_id=''):
    from apps.payments.models import Payment
    from apps.clients.models import Client
    from apps.packages.models import Package
    from apps.routers.models import MikroTikRouter, MikroTikJob
    try:
        sms_hash = hashlib.sha256(f"{phone}{sms_text}".encode()).hexdigest()
        if Payment.objects.filter(sms_hash=sms_hash).exists(): return
        parsed = parse_payment_sms(sms_text)
        if not parsed: return
        amount = parsed['amount']; reference = parsed['reference']; prefix = reference[:4].upper()
        try: client = Client.objects.get(reference_prefix=prefix, is_active=True)
        except Client.DoesNotExist:
            queue_sms(phone, f"Samahani, reference '{prefix}' haijulikani.\nSorry, reference '{prefix}' not found.", priority=5)
            return
        try: package = Package.objects.get(client=client, price=amount, is_active=True)
        except Package.DoesNotExist:
            prices = ', '.join([f"TZS {p.price:.0f}" for p in Package.objects.filter(client=client, is_active=True).order_by('price')])
            queue_sms(phone, f"Samahani, hakuna package ya TZS {amount:.0f}. Zinazopatikana: {prices}", priority=5)
            return
        router = MikroTikRouter.objects.filter(client=client).first()
        if not router: queue_sms(phone, "Samahani, router haijapatikana. Wasiliana na msambazaji.", priority=5); return
        commission = float(amount) * (float(client.commission_rate) / 100)
        payment = Payment.objects.create(client=client, phone_number=phone, amount=amount, reference_code=reference, network=network, device_id=device_id, raw_sms=sms_text, sms_hash=sms_hash, status='processing', commission_amount=commission, client_share=float(amount)-commission)
        MikroTikJob.objects.create(client=client, router=router, package=package, payment=payment, customer_phone=phone, action=MikroTikJob.ACTION_CREATE_VOUCHER, status=MikroTikJob.STATUS_PENDING)
        queue_sms(phone, f"Malipo ya TZS {amount:.0f} yamepokelewa. Voucher itatumwa hivi karibuni.\nPayment TZS {amount:.0f} received. Voucher coming soon.", priority=3)
        logger.info(f"✅ Job created for {router.name}")
    except Exception as e:
        logger.error(f"SMS processing error: {e}"); raise self.retry(countdown=60, exc=e)

@shared_task
def queue_voucher_sms(phone, code, package_name, duration, speed, payment_id=None):
    message = f"✅ Voucher yako:\nCode: {code}\nPackage: {package_name}\nMuda: {duration}\nKasi: {speed}\nUnganika WiFi kisha ingiza code.\nConnect WiFi then enter code."
    queue_sms(phone, message, priority=10)
    logger.info(f"Voucher SMS queued → {phone}: {code}")
