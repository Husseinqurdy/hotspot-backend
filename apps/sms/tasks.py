import re, hashlib, logging
from celery import shared_task

logger = logging.getLogger('hotspot')


def is_valid_phone(phone):
    """Angalia kama phone ni namba halisi si jina kama 'Vodacom' au 'M-PESA'."""
    return bool(re.match(r'^\+?\d{9,15}$', str(phone).strip()))


def extract_phone_from_sms(sms_text):
    """Toa namba ya simu kutoka SMS text."""
    # Tafuta 255XXXXXXXXX
    match = re.search(r'(255\d{9})', sms_text)
    if match:
        return '+' + match.group(1)
    # Tafuta 07XXXXXXXXX au 06XXXXXXXXX
    match = re.search(r'(0[67]\d{8})', sms_text)
    if match:
        return '+255' + match.group(1)[1:]
    return None


def parse_payment_sms(sms_text):
    PATTERNS = [
        (r'(\w{6,})\s+Imethibitishwa\.\s+Umelipwa\s+Tsh([\d,]+\.?\d*)', 'ref_first'),
        (r'Umelipa\s+Tsh([\d,]+\.?\d*).*?(?:Ref|ref)[:\s]+(\w{4,})', 'amount_first'),
        (r'Umelipa\s+TZS\s+([\d,]+)\s+kwa\s+\w+[.\s]+Kumbukumbu\s+namba\s+(\w+)', 'amount_first'),
        (r'TZS\s*([\d,]+\.?\d*)\s+paid\s+to\s+\w+\s+Ref\s+(\w+)', 'amount_first'),
        (r'Confirmed\.\s*TZS\s*([\d,]+)\s+sent.*?Ref[:\s]+(\w+)', 'amount_first'),
        (r'Confirmed\.\s+TZS([\d,]+)\s+sent\s+to[\w\s]+Ref[:\s]+(\w+)', 'amount_first'),
        (r'Malipo\s+ya\s+TZS\s+([\d,]+)\s+yamefanikiwa.*?kumbukumbu[:\s]+(\w+)', 'amount_first'),
        (r'(?:TZS|Tsh)[.\s]*([\d,]+).*?(?:Ref|ref|REF|kumbukumbu)[:\s]+(\w{4,})', 'amount_first'),
    ]

    for pattern, style in PATTERNS:
        m = re.search(pattern, sms_text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                if style == 'ref_first':
                    ref = m.group(1).upper().strip()
                    amount = float(m.group(2).replace(',', ''))
                else:
                    amount = float(m.group(1).replace(',', ''))
                    ref = m.group(2).upper().strip()

                if amount > 0 and len(ref) >= 4:
                    logger.info(f"SMS parsed: amount={amount}, ref={ref}")
                    return {'amount': amount, 'reference': ref}
            except:
                continue

    return None


def queue_sms(phone, message, priority=0):
    from apps.sms.models import OutgoingSMS
    # ✅ Hifadhi tu kama phone ni namba halisi
    if not is_valid_phone(phone):
        logger.warning(f"queue_sms skipped — phone si namba halisi: {phone}")
        return
    OutgoingSMS.objects.create(phone=phone, message=message, priority=priority)


@shared_task(bind=True, max_retries=2)
def process_payment_sms(self, phone, sms_text, network='unknown', device_id=''):
    from apps.payments.models import Payment, ClientPackagePrice
    from apps.routers.models import MikroTikRouter, MikroTikJob

    try:
        # ✅ Kama phone si namba halisi, toa kutoka SMS
        if not is_valid_phone(phone):
            extracted = extract_phone_from_sms(sms_text)
            if extracted:
                logger.info(f"Phone extracted from SMS: {extracted} (was: {phone})")
                phone = extracted
            else:
                logger.warning(f"Phone si namba halisi na haikupatikana kwenye SMS: {phone}")
                phone = None

        # ✅ Zuia duplicate
        sms_hash = hashlib.sha256(f"{phone}{sms_text}".encode()).hexdigest()
        if Payment.objects.filter(sms_hash=sms_hash).exists():
            logger.info(f"Duplicate SMS ignored: {sms_hash}")
            return

        # ✅ Parse SMS
        parsed = parse_payment_sms(sms_text)
        if not parsed:
            logger.warning(f"SMS haikuweza kusomwa: {sms_text[:80]}")
            if phone:
                queue_sms(
                    phone,
                    "Samahani, malipo yako hayakutambuliwa. "
                    "Hakikisha umelipa kiasi sahihi.\n"
                    "Sorry, your payment was not recognized.",
                    priority=5
                )
            return

        amount = int(parsed['amount'])
        reference = parsed['reference']

        logger.info(f"Payment SMS: phone={phone}, amount={amount}, ref={reference}")

        # ✅ Tafuta ClientPackagePrice kwa unique_amount
        try:
            cpp = ClientPackagePrice.objects.select_related(
                'client', 'package'
            ).get(unique_amount=amount, is_active=True)
        except ClientPackagePrice.DoesNotExist:
            logger.warning(f"Hakuna package ya kiasi {amount}")
            if phone:
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
            if phone:
                queue_sms(phone, "Samahani, huduma hii haipo. Wasiliana na msambazaji.", priority=5)
            return

        # ✅ Angalia package ni active
        if not package.is_active:
            logger.warning(f"Package {package.name} haipo active")
            if phone:
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
        router = MikroTikRouter.objects.filter(client=client, is_online=True).first()
        if not router:
            router = MikroTikRouter.objects.filter(client=client).first()
        if not router:
            if phone:
                queue_sms(
                    phone,
                    "Samahani, router haijapatikana. Wasiliana na msambazaji.",
                    priority=5
                )
            return

        # ✅ Hesabu commission
        commission = float(amount) * (float(client.commission_rate) / 100)
        client_share = float(amount) - commission

        # ✅ Tumia phone iliyopatikana au ile ya kwenye SMS
        customer_phone = phone or extract_phone_from_sms(sms_text) or 'unknown'

        # ✅ Unda Payment
        payment = Payment.objects.create(
            client=client,
            package=package,
            client_package_price=cpp,
            phone_number=customer_phone,
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
            customer_phone=customer_phone,
            action=MikroTikJob.ACTION_CREATE_VOUCHER,
            status=MikroTikJob.STATUS_PENDING,
        )

        if phone:
            queue_sms(
                phone,
                f"Malipo ya TZS {amount} yamepokelewa. Voucher itatumwa hivi karibuni.\n"
                f"Payment TZS {amount} received. Voucher coming soon.",
                priority=3
            )

        logger.info(
            f"✅ Job created — Client: {client.business_name} | "
            f"Package: {package.name} | Router: {router.name}"
        )

    except Exception as e:
        logger.error(f"SMS processing error: {e}")
        raise self.retry(countdown=60, exc=e)


@shared_task
def queue_voucher_sms(phone, code, package_name, duration, speed, payment_id=None):

    # SIMPLE GSM SAFE MESSAGE
    message = (
        f"Voucher: {code}\n"
        f"Package: {package_name}\n"
        f"Duration: {duration}\n"
        f"Speed: {speed}\n"
        f"Unganisha WiFi kisha ingiza voucher."
    )

    # REMOVE BAD CHARACTERS
    message = (
        message
        .replace('✅', '')
        .replace('\r', '')
    )

    queue_sms(phone, message[:150], priority=10)

    logger.info(f"Voucher SMS queued → {phone}: {code}")