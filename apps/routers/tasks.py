import random
import string
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('hotspot')


def generate_voucher_code():
    """Tengeneza code ya nasibu ya herufi 8."""
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=8))


@shared_task
def check_all_routers():
    from .models import MikroTikRouter
    from .mikrotik import get_mikrotik_connection
    from apps.sms.tasks import queue_sms

    routers = MikroTikRouter.objects.select_related('client').all()
    online = 0
    now = timezone.now()

    for r in routers:
        api = get_mikrotik_connection(r)
        alive = api.is_alive() if api else False
        if api: api.disconnect()

        was_online = r.is_online
        r.is_online = alive

        if alive:
            r.last_seen = now
            r.offline_alerted_at = None  # Reset alert ikirudi online
            online += 1
            r.save(update_fields=['is_online', 'last_seen', 'offline_alerted_at'])
        else:
            r.save(update_fields=['is_online'])

            # Tuma SMS kama:
            # 1. Router imekuwa online kabla (si mpya tu)
            # 2. SMS haijatumwa au ilitumwa zaidi ya saa 1 iliyopita
            should_alert = (
                was_online and
                r.client.phone and
                (
                    r.offline_alerted_at is None or
                    (now - r.offline_alerted_at).total_seconds() > 3600
                )
            )

            if should_alert:
                message = (
                    f"Tahadhari! Router yako '{r.name}' haipo online.\n"
                    f"Tafadhali angalia umeme au muunganiko wa internet.\n"
                    f"Router '{r.name}' is offline. Please check power or internet."
                )
                # MPYA: client=r.client ili SMS hii iingie kwenye queue
                # ya isolated ya client huyu.
                queue_sms(r.client.phone, message, priority=9, client=r.client)
                r.offline_alerted_at = now
                r.save(update_fields=['offline_alerted_at'])
                logger.info(f"📵 Offline SMS imetumwa kwa {r.client.phone} - Router: {r.name}")

    logger.info(f"Router check: {online}/{routers.count()} online")

@shared_task
def retry_failed_jobs():
    from .models import MikroTikJob
    failed = MikroTikJob.objects.filter(
        status='failed', retries__lt=3
    ).select_related('router')
    count = 0
    for job in failed:
        if job.router.is_online:
            job.status = MikroTikJob.STATUS_PENDING
            job.save(update_fields=['status'])
            count += 1
    if count:
        logger.info(f"Jobs {count} zimewekwa tena")


@shared_task
def process_pending_jobs():
    """
    Tekeleza MikroTik jobs zote zilizo pending.
    Inaitwa na Celery Beat kila dakika 1.

    MUHIMU — voucher moja kwenye routers kadhaa:
    Client mwenye routers zaidi ya moja anapata JOB MOJA KWA KILA ROUTER
    kwa malipo yale yale, zote zikiwa na `voucher_code` ile ile (imewekwa
    tayari na apps.sms.tasks.process_payment_sms). Job ya KWANZA
    kukamilika ndiyo inayounda rekodi ya `Voucher` (get_or_create);
    zilizobaki zinaongeza tu `VoucherRouterPresence` kwa router yao —
    hivyo hakuna IntegrityError kwa sababu ya code kufanana, na
    `DailySalesReport` bado inahesabu mauzo mara MOJA tu (Voucher moja).
    """
    from .models import MikroTikJob
    from .mikrotik import get_mikrotik_connection
    from apps.vouchers.models import Voucher, VoucherRouterPresence
    from apps.payments.models import Payment
    from apps.sms.tasks import queue_voucher_sms

    jobs = MikroTikJob.objects.filter(
        status=MikroTikJob.STATUS_PENDING
    ).select_related('router', 'package', 'client', 'payment')[:20]

    if not jobs:
        return

    logger.info(f"Processing {jobs.count()} pending jobs...")

    for job in jobs:
        try:
            # Weka status processing
            job.status = MikroTikJob.STATUS_PROCESSING
            job.save(update_fields=['status'])

            # Unganika MikroTik
            api = get_mikrotik_connection(job.router)
            if not api:
                logger.error(f"Job {job.id}: Router {job.router.name} haipo online")
                job.status = MikroTikJob.STATUS_FAILED
                job.error_message = "Router haipo online"
                job.retries += 1
                job.save(update_fields=['status', 'error_message', 'retries'])
                continue

            # Tumia voucher_code iliyowekwa tayari (routers kadhaa za
            # malipo yale yale zinashiriki code moja). Kama job hii
            # haina voucher_code (jobs za zamani / njia nyingine ya
            # kuunda job), tengeneza mpya kama fallback ya usalama.
            code = job.voucher_code
            if not code:
                code = generate_voucher_code()
                for _ in range(5):
                    existing = api.command(
                        '/ip/hotspot/user/print',
                        queries={'name': code}
                    )
                    if not existing:
                        break
                    code = generate_voucher_code()
                job.voucher_code = code
                job.save(update_fields=['voucher_code'])

            # Unda hotspot user kwenye MikroTik (router hii)
            profile = job.package.mikrotik_profile or 'default'
            comment = f"NetSafi|{job.client.business_name}|{job.customer_phone}"

            success = api.add_hotspot_user(
                username=code,
                password=code,
                profile=profile,
                comment=comment
            )

            api.disconnect()

            if not success:
                raise Exception("add_hotspot_user ilishindwa")

            # Hifadhi voucher kwenye database — get_or_create: job ya
            # KWANZA kwa code hii ndiyo inayounda Voucher; router
            # zingine (jobs zinazofuata za malipo yale yale) zinapata
            # ile ile Voucher iliyopo tayari, bila kujaribu kuiunda
            # upya (ambayo ingesababisha IntegrityError kwa unique code).
            # expires_at = None - itawekwa mteja atakapoingia (sync_voucher_status_from_mikrotik)
            voucher, voucher_created = Voucher.objects.get_or_create(
                code=code,
                defaults={
                    'client': job.client,
                    'router': job.router,
                    'package': job.package,
                    'payment': job.payment,
                    'customer_phone': job.customer_phone,
                    'status': 'active',
                    'expires_at': None,
                }
            )

            # Rekodi presence ya voucher hii kwenye ROUTER HII mahususi.
            VoucherRouterPresence.objects.get_or_create(
                voucher=voucher,
                router=job.router,
                defaults={'status': VoucherRouterPresence.STATUS_ACTIVE},
            )

            # Weka job completed
            job.status = MikroTikJob.STATUS_COMPLETED
            job.voucher_code = code
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'voucher_code', 'completed_at'])

            # Weka payment completed — fanya hivi kwa job ya KWANZA tu
            # itakayoifikia hali hii (zinazofuata zitakuta tayari
            # imeshakuwa completed, hakuna madhara ya kuiweka tena).
            if job.payment and job.payment.status != Payment.STATUS_COMPLETED:
                job.payment.status = Payment.STATUS_COMPLETED
                job.payment.processed_at = timezone.now()
                job.payment.save(update_fields=['status', 'processed_at'])

            # Tuma SMS ya voucher kwa mteja — MARA MOJA TU (job ya
            # kwanza iliyounda Voucher). Kama tutatuma kwa kila router,
            # mteja atapokea SMS zinazofanana mara kadhaa.
            if voucher_created:
                queue_voucher_sms.delay(
                    phone=job.customer_phone,
                    code=code,
                    package_name=job.package.name,
                    duration=job.package.duration_display(),
                    speed=f"{job.package.speed_down}Mbps/{job.package.speed_up}Mbps",
                    payment_id=job.payment.id if job.payment else None,
                )

            logger.info(
                f"✅ Job {job.id} completed — "
                f"Code: {code} | "
                f"Client: {job.client.business_name} | "
                f"Package: {job.package.name} | "
                f"Router: {job.router.name} | "
                f"Phone: {job.customer_phone} | "
                f"Voucher mpya: {voucher_created}"
            )

        except Exception as e:
            logger.error(f"❌ Job {job.id} failed: {e}")
            job.status = MikroTikJob.STATUS_FAILED
            job.error_message = str(e)
            job.retries += 1
            job.save(update_fields=['status', 'error_message', 'retries'])

            # Tuma SMS ya hitilafu kwa mteja
            try:
                from apps.sms.tasks import queue_sms
                # MPYA: client=job.client ili SMS hii iingie kwenye
                # queue sahihi ya isolated device ya client huyu.
                queue_sms(
                    job.customer_phone,
                    "Samahani, kulikuwa na hitilafu. "
                    "Tutajaribu tena hivi karibuni.\n"
                    "Sorry, there was an error. We will retry shortly.",
                    priority=5,
                    client=job.client,
                )
            except:
                pass


@shared_task
def sync_voucher_status_from_mikrotik():
    """
    Oanisha hali ya vouchers na schedulers za MikroTik.

    Kuna makundi MAWILI ya vouchers, yanayohitaji mantiki tofauti:

    (A) Vouchers ZENYE VoucherRouterPresence (zimeundwa na malipo —
        apps.sms.tasks.process_payment_sms — kwa client mwenye routers
        kadhaa, voucher moja inaweza kuwa na 'nakala' kwenye routers
        kadhaa). Kwa hizi: mteja anapotumia voucher kwenye router MOJA,
        tunafuta hotspot user kwenye routers ZINGINE zote zenye presence
        ya voucher hiyo hiyo.

    (B) Vouchers ZISIZO na presence YOYOTE (zimeundwa kwa mkono/batch
        kupitia VoucherManagementPage — router MOJA tu, Voucher.router
        ndiyo chanzo cha ukweli, kama ilivyokuwa kabla ya feature ya
        multi-router). Kwa hizi: HAKUNA kufuta routers zingine (hazipo),
        tunafanya TU yale ya awali — angalia scheduler kwenye router
        moja ya voucher, weka used_at/expires_at, na uweke 'expired'
        scheduler ikitoweka.

    MUHIMU SANA (bug iliyorekebishwa): kabla ya marekebisho haya, task
    hii ilikuwa ikipitia PRESENCE PEKEE — kundi (B) halikuguswa kabisa.
    Hii ilisababisha `Voucher.expires_at` ya vouchers za mkono kubaki
    kwenye default ya usalama iliyowekwa wakati wa kuundwa
    (`created_at + 2×duration_minutes`, angalia Voucher.save()) badala
    ya kusahihishwa kulingana na wakati HALISI wa matumizi — na hivyo
    `expire_old_vouchers` (Celery, kila saa) ilikuwa ikizifuta MAPEMA
    SANA, ikiondoa hotspot user pekee (scheduler ya on-login ikibaki,
    kwa sababu haikuwahi kufika kwenye muda wake wa kweli).

    FIX YA PILI (sync_missing_since — 'false negative' kutoka MikroTik):
    Kundi (B) awali lilikuwa likiamini USOMAJI MMOJA tu wa
    '/system/scheduler/print' kuamua kama voucher imeisha — kama code
    yake haikuonekana kwenye orodha iliyorudi, voucher iliwekwa
    'expired' PAPO HAPO. Uchunguzi ulionyesha kwamba wakati mwingine
    muunganiko wa MikroTik (hasa kwa mzunguko unaosoma routers/vouchers
    nyingi kwa muda mfupi) unarudisha orodha isiyokamilika BILA kutupa
    exception — voucher halali kabisa (ambayo scheduler yake bado ipo
    kwenye router) inaonekana 'haipo' kwa bahati mbaya, na kufutwa
    kimakosa dakika/masaa kabla ya wakati wake halisi (mfano: NEQH,
    67BG, FCMT, YXFU, 4294).

    Sasa voucher 'isiyoonekana' HAIFUTWI papo hapo — inawekewa alama
    (Voucher.sync_missing_since) na kuthibitishwa tena mzunguko
    unaofuata (dakika 1 baadaye) kabla ya kuifanya 'expired'. Ikiwa
    itaonekana tena kabla ya uthibitisho, alama inafutwa (ilikuwa ni
    hitilafu ya mara moja tu). Hii inaongeza ucheleweshaji mdogo (~dakika
    1) kwa vouchers zinazoisha KWELI, lakini inazuia kufutwa mapema
    kimakosa kwa vouchers zenye hitilafu ya muunganiko ya mara moja.
    """
    from apps.vouchers.models import Voucher, VoucherRouterPresence
    from .mikrotik import get_mikrotik_connection

    now = timezone.now()

    # ── (A) presence-based vouchers ───────────────────────────────
    active_presences = list(
        VoucherRouterPresence.objects.filter(
            status=VoucherRouterPresence.STATUS_ACTIVE
        ).select_related('router', 'voucher', 'voucher__package')
    )

    # ── (B) legacy/manual vouchers — HAZINA presence yoyote (hata
    # 'removed') — hii ndiyo njia sahihi ya kuzitambua bila kujali
    # status ya presence, kwa sababu voucher ya mkono kamwe haitakuwa
    # na presence yoyote kabisa. ──
    voucher_ids_with_any_presence = set(
        VoucherRouterPresence.objects.values_list('voucher_id', flat=True)
    )
    legacy_vouchers = list(
        Voucher.objects.filter(status='active')
        .exclude(id__in=voucher_ids_with_any_presence)
        .select_related('router', 'package')
    )

    if not active_presences and not legacy_vouchers:
        return

    # ── Router → schedulers: soma kila router MOJA TU (kundi A na B
    # zikichangia orodha moja ya routers zinazohitajika) ──
    routers_needed = {}
    for presence in active_presences:
        routers_needed[presence.router_id] = presence.router
    for voucher in legacy_vouchers:
        routers_needed[voucher.router_id] = voucher.router

    scheduler_names_by_router = {}
    for router_id, router in routers_needed.items():
        try:
            api = get_mikrotik_connection(router)
            if not api:
                logger.warning(f"Router {router.name} haipo online - skip")
                continue
            try:
                schedulers = api.command('/system/scheduler/print')
                scheduler_names_by_router[router_id] = {s.get('name', '') for s in schedulers}
            except Exception as e:
                logger.error(f"Imeshindwa kusoma schedulers kutoka {router.name}: {e}")
            finally:
                api.disconnect()
        except Exception as e:
            logger.error(f"sync_voucher_status: connection error {router.name}: {e}")

    # ═══════════════════════════════════════════════════════════
    # (B) LEGACY / MANUAL — mantiki ya ZAMANI, router MOJA tu
    # ═══════════════════════════════════════════════════════════
    legacy_used_count = 0
    for voucher in legacy_vouchers:
        scheduler_names = scheduler_names_by_router.get(voucher.router_id)
        if scheduler_names is None:
            continue  # router haikufikika mzunguko huu

        if voucher.code in scheduler_names:
            if voucher.used_at is None:
                voucher.used_at = now
                voucher.expires_at = now + timezone.timedelta(
                    minutes=voucher.package.duration_minutes
                )
                voucher.save(update_fields=['used_at', 'expires_at'])
                legacy_used_count += 1
                logger.info(
                    f"✅ Voucher {voucher.code} (manual) imeanza kutumika - "
                    f"itaisha: {voucher.expires_at}"
                )
            elif voucher.sync_missing_since is not None:
                # Ilikuwa 'imekosekana' mzunguko uliopita, lakini sasa
                # imeonekana tena — ilikuwa false alarm (hitilafu ya
                # muunganiko), si kuisha kwa kweli. Futa alama.
                voucher.sync_missing_since = None
                voucher.save(update_fields=['sync_missing_since'])
        else:
            if voucher.used_at is not None:
                if voucher.sync_missing_since is None:
                    # Mara ya KWANZA kuikosa — usiifute bado. Weka alama
                    # tu, tuithibitishe tena mzunguko unaofuata (dakika 1)
                    # kabla ya kuiamini imekwisha kweli.
                    voucher.sync_missing_since = now
                    voucher.save(update_fields=['sync_missing_since'])
                    logger.warning(
                        f"⚠️ Voucher {voucher.code} (manual) haionekani kwenye "
                        f"schedulers za {voucher.router.name} — inasubiri "
                        f"uthibitisho mzunguko ujao"
                    )
                else:
                    # Mara ya PILI mfululizo kuikosa — sasa tunaithibitisha
                    # imekwisha kweli.
                    voucher.status = 'expired'
                    voucher.sync_missing_since = None
                    voucher.save(update_fields=['status', 'sync_missing_since'])
                    logger.info(f"✅ Voucher {voucher.code} (manual) imeisha - imewekwa expired")

    # ═══════════════════════════════════════════════════════════
    # (A) PRESENCE-BASED — routers kadhaa, kama ilivyoongezwa hivi karibuni
    # ═══════════════════════════════════════════════════════════
    routers_map = {}
    for presence in active_presences:
        rid = presence.router_id
        if rid not in routers_map:
            routers_map[rid] = {'router': presence.router, 'presences': []}
        routers_map[rid]['presences'].append(presence)

    # ── Hatua 1: tambua ni presence zipi zimetumika (scheduler ipo) ──
    used_presences = []  # [(presence, router)]
    for router_id, data in routers_map.items():
        scheduler_names = scheduler_names_by_router.get(router_id)
        if scheduler_names is None:
            continue  # router haikufikika mzunguko huu
        for presence in data['presences']:
            if presence.voucher.code in scheduler_names:
                used_presences.append(presence)

    for presence in used_presences:
        voucher = presence.voucher
        router = presence.router

        if voucher.used_at is None:
            voucher.used_at = now
            voucher.expires_at = now + timezone.timedelta(
                minutes=voucher.package.duration_minutes
            )
            voucher.router = router
            voucher.save(update_fields=['used_at', 'expires_at', 'router'])
            logger.info(
                f"✅ Voucher {voucher.code} imeanza kutumika kwenye {router.name} - "
                f"itaisha: {voucher.expires_at}"
            )

        # ── Futa hotspot user kwenye ROUTERS ZINGINE zote zenye presence
        # 'active' ya voucher hii hii (mteja ametumia router moja tu) ──
        other_presences = VoucherRouterPresence.objects.filter(
            voucher=voucher,
            status=VoucherRouterPresence.STATUS_ACTIVE,
        ).exclude(router_id=router.id).select_related('router')

        for other in other_presences:
            other_router = other.router
            try:
                api = get_mikrotik_connection(other_router)
                if not api:
                    logger.warning(
                        f"sync_voucher_status: {other_router.name} haipo online — "
                        f"itajaribu kufuta {voucher.code} mzunguko ujao"
                    )
                    continue
                removed = api.remove_hotspot_user(voucher.code)
                api.disconnect()

                if removed:
                    other.status = VoucherRouterPresence.STATUS_REMOVED
                    other.removed_at = now
                    other.save(update_fields=['status', 'removed_at'])
                    logger.info(
                        f"🗑️ Voucher {voucher.code} imefutwa kwenye {other_router.name} "
                        f"— ilishatumika kwenye {router.name}"
                    )
                else:
                    logger.warning(
                        f"sync_voucher_status: kufuta {voucher.code} kwenye "
                        f"{other_router.name} hakukufanikiwa — itajaribu tena"
                    )
            except Exception as e:
                logger.error(
                    f"sync_voucher_status: error kufuta {voucher.code} kwenye "
                    f"{other_router.name}: {e}"
                )

    # ── Hatua 2: vouchers zilizoisha muda kwenye router walipotumia ──
    # (presence ambayo BADO ni 'active' kwenye router = Voucher.router,
    # lakini scheduler yake imeshatoweka = muda umeisha)
    used_presence_ids = {p.id for p in used_presences}
    for router_id, data in routers_map.items():
        scheduler_names = scheduler_names_by_router.get(router_id)
        if scheduler_names is None:
            continue
        for presence in data['presences']:
            if presence.id in used_presence_ids:
                continue  # bado inatumika sasa hivi, si kesi hii
            voucher = presence.voucher
            is_used_router = (
                voucher.used_at is not None and voucher.router_id == presence.router_id
            )
            if is_used_router and voucher.code not in scheduler_names:
                voucher.status = 'expired'
                voucher.save(update_fields=['status'])
                logger.info(f"✅ Voucher {voucher.code} imeisha - imewekwa expired")

    logger.info(
        f"sync_voucher_status_from_mikrotik: legacy vouchers {len(legacy_vouchers)} "
        f"(mpya zilizoanza kutumika: {legacy_used_count}), "
        f"presence routers {len(routers_map)}, "
        f"presence vouchers zilizoanza kutumika {len(used_presences)}"
    )

