import re, hashlib, logging
from celery import shared_task

logger = logging.getLogger('hotspot')


def is_valid_phone(phone):
    """Angalia kama phone ni namba halisi si jina kama 'Vodacom' au 'M-PESA'."""
    return bool(re.match(r'^\+?\d{9,15}$', str(phone).strip()))


def extract_phone_from_sms(sms_text):
    """Toa namba ya simu kutoka SMS text."""
    match = re.search(r'(255\d{9})', sms_text)
    if match:
        return '+' + match.group(1)
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


def queue_sms(phone, message, priority=0, client=None):
    """
    'client' inaamua ni kifaa gani (GSMDevice) hatimaye kitachukua na
    kutuma huu ujumbe, kwa sababu OutgoingSMSView inachuja queue kwa
    client wa kifaa kinachouliza (mmiliki AU mmoja wa shared_with).

    Ikiwa client=None (call site ya zamani ambayo bado
    haijasasishwa), ujumbe unahifadhiwa bila client na HAUTACHUKULIWA
    na kifaa chochote kwenye mfumo mpya wa isolated devices.
    """
    from apps.sms.models import OutgoingSMS
    if not is_valid_phone(phone):
        logger.warning(f"queue_sms skipped — phone si namba halisi: {phone}")
        return
    if client is None:
        logger.warning(
            f"queue_sms: client haijapitishwa (phone={phone}) — ujumbe "
            f"huu HAUTACHUKULIWA na kifaa chochote kwenye mfumo wa "
            f"isolated devices mpaka call site hii isasishwe."
        )
    OutgoingSMS.objects.create(phone=phone, message=message, priority=priority, client=client)


def _generate_shared_voucher_code():
    """
    Tengeneza voucher code ya PAMOJA itakayotumika kwenye jobs ZOTE
    (router zote) za malipo haya moja.
    """
    from apps.routers.tasks import generate_voucher_code
    from apps.vouchers.models import Voucher

    for _ in range(10):
        code = generate_voucher_code()
        if not Voucher.objects.filter(code=code).exists():
            return code
    return generate_voucher_code() + generate_voucher_code()[:2]


@shared_task(bind=True, max_retries=2)
def process_payment_sms(self, phone, sms_text, network='unknown', device_id=''):
    from apps.payments.models import Payment, ClientPackagePrice
    from apps.devices.models import GSMDevice
    from apps.routers.models import MikroTikRouter, MikroTikJob

    try:
        # ✅ MUHIMU — MSINGI WA ISOLATION: device_id ndiyo chanzo cha
        # kwanza cha ukweli kuhusu ni CLIENT(S) gani anahusika. Bila
        # kifaa kinachotambulika, HATUENDELEI KABISA.
        if not device_id:
            logger.warning("process_payment_sms: hakuna device_id — SMS imekataliwa (haiwezekani kujua client)")
            return

        try:
            device = GSMDevice.objects.select_related('client').prefetch_related('shared_with').get(
                device_id=device_id, is_active=True
            )
        except GSMDevice.DoesNotExist:
            logger.warning(f"process_payment_sms: GSMDevice haipatikani device_id={device_id}")
            return

        # ✅ MPYA: kundi la clients wanaoruhusiwa kutumia kifaa hiki —
        # mmiliki mkuu PAMOJA na wowote kwenye shared_with (kwa hiari).
        # Kwa kifaa cha kawaida (bila sharing), hii ni client MMOJA
        # tu — sawa kabisa na tabia ya awali.
        eligible_clients = list(device.eligible_clients())
        eligible_client_ids = [c.id for c in eligible_clients]

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
                # Kifaa kisicho na sharing kina client mmoja tu wa
                # kutumia hapa; kikiwa na sharing, tunatumia mmiliki
                # mkuu kama default ya kutumia kutuma taarifa hii.
                queue_sms(
                    phone,
                    "Samahani, malipo yako hayakutambuliwa. "
                    "Hakikisha umelipa kiasi sahihi.\n"
                    "Sorry, your payment was not recognized.",
                    priority=5,
                    client=device.client,
                )
            return

        amount = int(parsed['amount'])
        reference = parsed['reference']

        logger.info(
            f"Payment SMS: device={device.device_id}, "
            f"eligible_clients={[c.business_name for c in eligible_clients]}, "
            f"phone={phone}, amount={amount}, ref={reference}"
        )

        # ✅ Tafuta ClientPackagePrice ndani ya eligible_clients —
        # SIYO tena kwa unique_amount peke yake mfumo mzima, wala
        # siyo lazima client mmoja pekee — ni KUNDI la kifaa hiki.
        # Kwa kifaa kisicho na sharing, hii ni sawa na
        # client=device.client moja kwa moja.
        try:
            cpp = ClientPackagePrice.objects.select_related(
                'client', 'package'
            ).get(client_id__in=eligible_client_ids, unique_amount=amount, is_active=True)
        except ClientPackagePrice.DoesNotExist:
            logger.warning(f"Hakuna package ya kiasi {amount} kwa eligible_clients={eligible_client_ids}")
            if phone:
                queue_sms(
                    phone,
                    f"Samahani, hakuna package ya TZS {amount}. "
                    f"Tafadhali wasiliana na msambazaji wako.\n"
                    f"Sorry, no package found for TZS {amount}.",
                    priority=5,
                    client=device.client,
                )
            return
        except ClientPackagePrice.MultipleObjectsReturned:
            # Hii haipaswi kutokea kwa sababu ya unique_together
            # (client, unique_amount) — lakini kama clients wawili
            # WANAOSHIRIKIANA kifaa wote wana amount ile ile (mgongano
            # ambao Package.clean() ilipaswa kuuzuia), tunakataa
            # kuchagua kwa bahati na kulog error badala yake.
            logger.error(
                f"MGONGANO: amount={amount} inalingana na zaidi ya "
                f"ClientPackagePrice moja ndani ya eligible_clients="
                f"{eligible_client_ids}. Hii inaonyesha Package.clean() "
                f"validation ilipita kimakosa — angalia mara moja."
            )
            if phone:
                queue_sms(
                    phone,
                    "Samahani, kuna hitilafu ya kiufundi. Wasiliana na msambazaji.",
                    priority=5,
                    client=device.client,
                )
            return

        client = cpp.client
        package = cpp.package

        # ✅ Angalia client ni active
        if not client.is_active:
            logger.warning(f"Client {client.business_name} amezuiwa")
            if phone:
                queue_sms(phone, "Samahani, huduma hii haipo. Wasiliana na msambazaji.", priority=5, client=client)
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
                    priority=5,
                    client=client,
                )
            return

        # ✅ Tafuta routers ZOTE za client
        routers = list(MikroTikRouter.objects.filter(client=client, is_online=True))
        if not routers:
            fallback = MikroTikRouter.objects.filter(client=client).first()
            routers = [fallback] if fallback else []

        if not routers:
            if phone:
                queue_sms(
                    phone,
                    "Samahani, router haijapatikana. Wasiliana na msambazaji.",
                    priority=5,
                    client=client,
                )
            return

        # ✅ Hesabu commission
        commission = float(amount) * (float(client.commission_rate) / 100)
        client_share = float(amount) - commission

        customer_phone = phone or extract_phone_from_sms(sms_text) or 'unknown'

        # ✅ Unda Payment
        payment = Payment.objects.create(
            client=client,
            package=package,
            client_package_price=cpp,
            gsm_device=device,
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

        from django.db.models import F
        client.__class__.objects.filter(pk=client.pk).update(
            balance=F('balance') + client_share
        )

        voucher_code = _generate_shared_voucher_code()

        created_jobs = []
        for router in routers:
            job = MikroTikJob.objects.create(
                client=client,
                router=router,
                package=package,
                payment=payment,
                customer_phone=customer_phone,
                action=MikroTikJob.ACTION_CREATE_VOUCHER,
                status=MikroTikJob.STATUS_PENDING,
                voucher_code=voucher_code,
            )
            created_jobs.append(job)

        if phone:
            queue_sms(
                phone,
                f"Malipo ya TZS {amount} yamepokelewa. Voucher itatumwa hivi karibuni.\n"
                f"Payment TZS {amount} received. Voucher coming soon.",
                priority=3,
                client=client,
            )

        router_names = ', '.join(r.name for r in routers)
        logger.info(
            f"✅ Jobs {len(created_jobs)} zimeundwa — "
            f"Client: {client.business_name} | "
            f"Package: {package.name} | "
            f"Routers: {router_names} | "
            f"Voucher code: {voucher_code}"
        )

    except Exception as e:
        logger.error(f"SMS processing error: {e}")
        raise self.retry(countdown=60, exc=e)


@shared_task
def queue_voucher_sms(phone, code, package_name, duration, speed, payment_id=None, client=None):
    message = (
        f"Voucher: {code}\n"
        f"Package: {package_name}\n"
        f"Duration: {duration}\n"
        f"Speed: {speed}\n"
        f"Unganisha WiFi kisha ingiza voucher."
    )

    message = (
        message
        .replace('✅', '')
        .replace('\r', '')
    )

    if client is None and payment_id:
        try:
            from apps.payments.models import Payment
            client = Payment.objects.only('client_id').get(pk=payment_id).client
        except Exception:
            pass

    queue_sms(phone, message[:150], priority=10, client=client)

    logger.info(f"Voucher SMS queued → {phone}: {code}")
