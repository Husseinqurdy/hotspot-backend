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
                amount = float(m.group(1).replace(',', ''))
                ref = m.group(2).upper().strip()
                if amount > 0 and len(ref) >= 4:
                    return {'amount': amount, 'reference': ref}
            except:
                continue
    return None


def queue_sms(phone, message, priority=0):
    from apps.sms.models import OutgoingSMS
    OutgoingSMS.objects.create(phone=phone, message=message, priority=priority)


@shared_task(bind=True, max_retries=2)
def process_payment_sms(self, phone, sms_text, network='unknown', device_id=''):
    from apps.payments.models import Payment, ClientPackagePrice
    from apps.routers.models import MikroTikRouter, MikroTikJob

    try:
        # ✅ Zuia duplicate
        sms_hash = hashlib.sha256(f"{phone}{sms_text}".encode()).hexdigest()
        if Payment.objects.filter(sms_hash=sms_hash).exists():
            logger.info(f"Duplicate SMS ignored: {sms_hash}")
            return

        # ✅ Parse SMS
        parsed = parse_payment_sms(sms_text)
        if not parsed:
            logger.warning(f"SMS haikuweza kusomwa: {sms_text[:50]}")
            return

        amount = int(parsed['amount'])
        reference = parsed['reference']

        # ✅ Tafuta ClientPackagePrice kwa unique_amount
        try:
            cpp = ClientPackagePrice.objects.select_related(
                'client', 'package'
            ).get(unique_amount=amount, is_active=True)
        except ClientPackagePrice.DoesNotExist:
            logger.warning(f"Hakuna package ya kiasi {amount}")
            queue_sms(
                phone,
                f"Samahani, hakuna package ya TZS {amount}. "
                f"Tafadhali wasiliana na msambazaji wako.\n"
                f"Sorry, no package found for TZS {amount}.",
                priority=5
            )
            return

        client = cpp.client
        package = cpp.package

        # ✅ Angalia client ni active
        if not client.is_active:
            logger.warning(f"Client {client.business_name} amezuiwa")
            queue_sms(phone, "Samahani, huduma hii haipo. Wasiliana na msambazaji.", priority=5)
            return

        # ✅ Angalia package ni active
        if not package.is_active:
            logger.warning(f"Package {package.name} haipo active")
            active_prices = ', '.join([
                f"TZS {c.unique_amount}"
                for c in ClientPackagePrice.objects.filter(
                    client=client, is_active=True
                ).order_by('unique_amount')
            ])
            queue_sms(
                phone,
                f"Samahani, package hii haipo tena. "
                f"Zinazopatikana: {active_prices}",
                priority=5
            )
            return

        # ✅ Tafuta router
        router = MikroTikRouter.objects.filter(
            client=client, is_online=True
        ).first()

        if not router:
            # Jaribu router yoyote hata kama offline
            router = MikroTikRouter.objects.filter(client=client).first()

        if not router:
            queue_sms(
                phone,
                "Samahani, router haijapatikana. Wasiliana na msambazaji.",
                priority=5
            )
            return

        # ✅ Hesabu commission
        commission = float(amount) * (float(client.commission_rate) / 100)
        client_share = float(amount) - commission

        # ✅ Unda Payment
        payment = Payment.objects.create(
            client=client,
            package=package,
            client_package_price=cpp,
            phone_number=phone,
            amount=amount,
            transaction_id=reference,
            network=network,
            device_id=device_id,
            raw_sms=sms_text,
            sms_hash=sms_hash,
            status=Payment.STATUS_PROCESSING,
            commission_amount=commission,
            client_share=client_share,
        )

        # ✅ Unda Job
        MikroTikJob.objects.create(
            client=client,
            router=router,
            package=package,
            payment=payment,
            customer_phone=phone,
            action=MikroTikJob.ACTION_CREATE_VOUCHER,
            status=MikroTikJob.STATUS_PENDING,
        )

        queue_sms(
            phone,
            f"Malipo ya TZS {amount} yamepokelewa. Voucher itatumwa hivi karibuni.\n"
            f"Payment TZS {amount} received. Voucher coming soon.",
            priority=3
        )

        logger.info(f"✅ Job created — Client: {client.business_name} | Package: {package.name} | Router: {router.name}")

    except Exception as e:
        logger.error(f"SMS processing error: {e}")
        raise self.retry(countdown=60, exc=e)


@shared_task
def queue_voucher_sms(phone, code, package_name, duration, speed, payment_id=None):
    message = (
        f"✅ Voucher yako:\n"
        f"Code: {code}\n"
        f"Package: {package_name}\n"
        f"Muda: {duration}\n"
        f"Kasi: {speed}\n"
        f"Unganika WiFi kisha ingiza code.\n"
        f"Connect WiFi then enter code."
    )
    queue_sms(phone, message, priority=10)
    logger.info(f"Voucher SMS queued → {phone}: {code}")