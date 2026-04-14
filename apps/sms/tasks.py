import re
import hashlib
import logging
from celery import shared_task

logger = logging.getLogger('netsafi')


def parse_payment_sms(sms_text: str) -> dict | None:
    """Chambua SMS ya malipo kutoka mitandao yote ya Tanzania."""
    PATTERNS = [
        r'TZS\s*([\d,]+\.?\d*)\s+paid\s+to\s+\w+\s+Ref\s+(\w+)',
        r'Confirmed\.\s*TZS\s*([\d,]+)\s+sent.*?Ref[:\s]+(\w+)',
        r'Umelipa\s+TZS\s+([\d,]+)\s+kwa\s+\w+[.\s]+Kumbukumbu\s+namba\s+(\w+)',
        r'Confirmed\.\s+TZS([\d,]+)\s+sent\s+to[\w\s]+Ref[:\s]+(\w+)',
        r'Malipo\s+ya\s+TZS\s+([\d,]+)\s+yamefanikiwa.*?kumbukumbu[:\s]+(\w+)',
        r'(?:TZS|Tsh)[.\s]*([\d,]+).*?(?:Ref|ref|REF|kumbukumbu|Kumb)[:\s]+(\w{4,})',
    ]
    for pattern in PATTERNS:
        match = re.search(pattern, sms_text, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                amount = float(match.group(1).replace(',', ''))
                reference = match.group(2).upper().strip()
                if amount > 0 and len(reference) >= 4:
                    return {'amount': amount, 'reference': reference}
            except (ValueError, IndexError):
                continue
    return None


def get_sms_hash(phone: str, text: str) -> str:
    return hashlib.sha256(f"{phone}{text}".encode()).hexdigest()


def queue_sms(phone: str, message: str, priority: int = 0):
    """
    Weka SMS kwenye queue itakayotumwa na A7670E device.
    Haitumii Africa's Talking - A7670 ndiyo inatuma.
    """
    from apps.sms.models import OutgoingSMS
    OutgoingSMS.objects.create(
        phone=phone,
        message=message,
        priority=priority,
    )
    logger.info(f"SMS queued → {phone}")


@shared_task(bind=True, max_retries=2)
def process_payment_sms(self, phone: str, sms_text: str, network: str = 'unknown', device_id: str = ''):
    """
    Chambua SMS ya malipo na unda MikroTikJob.
    MikroTik itachukua job kupitia VPN na kutekeleza.
    """
    from apps.payments.models import Payment
    from apps.clients.models import Client
    from apps.packages.models import Package
    from apps.routers.models import MikroTikRouter, MikroTikJob

    try:
        # 1. Duplicate check
        sms_hash = get_sms_hash(phone, sms_text)
        if Payment.objects.filter(sms_hash=sms_hash).exists():
            logger.info(f"Duplicate SMS inapuuzwa: {phone}")
            return

        # 2. Chambua SMS
        parsed = parse_payment_sms(sms_text)
        if not parsed:
            logger.info(f"SMS si ya malipo: {sms_text[:60]}")
            return

        amount = parsed['amount']
        reference = parsed['reference']
        prefix = reference[:4].upper()

        logger.info(f"Malipo: TZS {amount} | Ref: {reference} | Network: {network}")

        # 3. Tambua client kwa prefix
        try:
            client = Client.objects.get(reference_prefix=prefix, is_active=True)
        except Client.DoesNotExist:
            logger.warning(f"Client hajapatikana kwa prefix: {prefix}")
            queue_sms(
                phone,
                f"Samahani, reference '{prefix}' haijulikani. Wasiliana na msambazaji wako.\n"
                f"Sorry, reference '{prefix}' not found. Contact your provider.",
                priority=5
            )
            return

        # 4. Tafuta package
        try:
            package = Package.objects.get(client=client, price=amount, is_active=True)
        except Package.DoesNotExist:
            available = Package.objects.filter(client=client, is_active=True).order_by('price')
            prices = ', '.join([f"TZS {p.price:.0f}" for p in available])
            queue_sms(
                phone,
                f"Samahani, hakuna package ya TZS {amount:.0f}. Zinazopatikana: {prices}\n"
                f"Sorry, no package for TZS {amount:.0f}. Available: {prices}",
                priority=5
            )
            return

        # 5. Pata router ya client
        router = MikroTikRouter.objects.filter(client=client).first()
        if not router:
            logger.error(f"Hakuna router kwa {client}")
            queue_sms(phone, "Samahani, router haijapatikana. Wasiliana na msambazaji wako.", priority=5)
            return

        # 6. Hifadhi payment
        commission = float(amount) * (float(client.commission_rate) / 100)
        client_share = float(amount) - commission

        payment = Payment.objects.create(
            client=client,
            phone_number=phone,
            amount=amount,
            reference_code=reference,
            network=network,
            device_id=device_id,
            raw_sms=sms_text,
            sms_hash=sms_hash,
            status='processing',
            commission_amount=commission,
            client_share=client_share,
        )

        # 7. Unda MikroTikJob - MikroTik itachukua kupitia VPN
        MikroTikJob.objects.create(
            client=client,
            router=router,
            package=package,
            payment=payment,
            customer_phone=phone,
            action=MikroTikJob.ACTION_CREATE_VOUCHER,
            status=MikroTikJob.STATUS_PENDING,
        )

        # 8. Tuma SMS ya uthibitisho - malipo yamepokelewa
        queue_sms(
            phone,
            f"Malipo ya TZS {amount:.0f} yamepokelewa kwa {package.name}. "
            f"Voucher yako itatumwa hivi karibuni.\n"
            f"Payment TZS {amount:.0f} received for {package.name}. "
            f"Your voucher will be sent shortly.",
            priority=3
        )

        logger.info(f"✅ Job imeundwa kwa {router.name} - inasubiri MikroTik via VPN")

    except Exception as e:
        logger.error(f"SMS processing error: {e}")
        raise self.retry(countdown=60, exc=e)


@shared_task
def queue_voucher_sms(phone, code, package_name, duration, speed, payment_id=None):
    """
    Weka SMS ya voucher kwenye queue.
    A7670E itaituma yenyewe kupitia SIM card yake.
    """
    message = (
        f"✅ Voucher yako / Your Voucher:\n"
        f"Code: {code}\n"
        f"Package: {package_name}\n"
        f"Muda/Time: {duration}\n"
        f"Kasi/Speed: {speed}\n"
        f"Unganika WiFi kisha ingiza code.\n"
        f"Connect WiFi then enter code."
    )
    queue_sms(phone, message, priority=10)  # Priority ya juu - voucher ni muhimu
    logger.info(f"Voucher SMS queued → {phone}: {code}")
