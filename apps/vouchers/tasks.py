from datetime import datetime
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger('netsafi')

_MT_MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


def _parse_mikrotik_datetime(start_date: str, start_time: str):
    """
    MikroTik inarudisha start-date kama 'jul/13/2026' na start-time kama
    '14:32:07'. Hii ndiyo WAKATI HALISI scheduler ilipoundwa (yaani wakati
    mteja aliingiza voucher) — siyo wakati sisi tunapopiga poll. Tunatumia
    hii badala ya timezone.now() ili ripoti iwe sahihi hata kama router
    ilikuwa offline kwa muda mrefu kabla hatujaigundua.
    Inarudisha None ikiwa format haieleweki (tutarudi kwenye now() salama).
    """
    try:
        mon_str, day_str, year_str = start_date.split('/')
        month = _MT_MONTHS.get(mon_str.strip().lower())
        if not month:
            return None
        day, year = int(day_str), int(year_str)
        hour, minute, second = (int(x) for x in start_time.strip().split(':'))
        naive = datetime(year, month, day, hour, minute, second)
        return timezone.make_aware(naive, timezone.get_current_timezone())
    except Exception:
        return None


@shared_task
def expire_old_vouchers():
    from .models import Voucher
    from apps.routers.mikrotik import get_mikrotik_connection
    expired = Voucher.objects.filter(
    status='active',
    expires_at__lt=timezone.now(),
    used_at__isnull=False  # ← Expire tu vouchers ambazo mteja ameshaingia
    ).select_related('router')
    count = 0
    for v in expired:
        api = get_mikrotik_connection(v.router)
        if api: api.remove_hotspot_user(v.code); api.disconnect()
        v.status = 'expired'; v.save(update_fields=['status']); count += 1
<<<<<<< HEAD
    logger.info(f"Expired {count} vouchers")


@shared_task
def send_voucher_expiry_reminders():
    """
    Tuma SMS ya onyo kwa wateja ambao voucher yao itaisha ndani ya dakika 30.
    Inaitwa na Celery Beat kila dakika 5.
    """
    from .models import Voucher
    from apps.sms.tasks import queue_sms

    now = timezone.now()
    warning_time = now + timezone.timedelta(minutes=30)

    # Pata vouchers zinazokaribia kuisha - ndani ya dakika 30 - na reminder haijatumwa
    vouchers = Voucher.objects.filter(
        status='active',
        reminder_sent=False,
        expires_at__isnull=False,
        expires_at__lte=warning_time,
        expires_at__gt=now,
    ).select_related('package')

    count = 0
    for voucher in vouchers:
        try:
            # Hesabu muda uliobaki
            remaining = voucher.expires_at - now
            minutes_left = int(remaining.total_seconds() / 60)

            message = (
                f"Voucher yako {voucher.code} itaisha baada ya dakika {minutes_left}.\n"
                f"Nunua upya ili kuendelea na internet.\n"
                f"Your voucher expires in {minutes_left} minutes."
            )

            # MPYA: client=voucher.client ili reminder hii iingie
            # kwenye queue sahihi ya isolated device ya client huyu.
            queue_sms(voucher.customer_phone, message, priority=8, client=voucher.client)

            voucher.reminder_sent = True
            voucher.save(update_fields=['reminder_sent'])
            count += 1

        except Exception as e:
            logger.error(f"Reminder SMS failed kwa {voucher.code}: {e}")

    if count:
        logger.info(f"✅ Reminder SMS {count} zimetumwa")


@shared_task
def check_voucher_usage():
    """
    Inakimbia kila dakika chache (Celery Beat). Kwa kila router iliyo online,
    inaangalia orodha ya schedulers kwenye MikroTik — voucher inayotumika
    na mteja huunda scheduler yenye jina sawa na code yake (angalia
    Package._sync_to_mikrotik on_login_script: "name=$voucher").

    Voucher yoyote ya ndani ya DB (status='active', used_at bado null)
    ambayo code yake inaonekana kwenye orodha hiyo ya schedulers —
    inamaanisha imeshatumika. Tunaweka used_at na kutuma notification.

    MUHIMU: routers hazichujwi kwa `is_online` (flag ya DB inayoweza kuwa
    "stale"/isiyoaminika kutokana na muunganiko wa VPN unaokatika mara kwa
    mara — angalia logs za "MikroTik connect failed: timed out"). Badala
    yake, tunapata routers moja kwa moja kutoka kwenye vouchers zenye kazi
    halisi inayosubiri (used_at bado null), kisha tunajaribu kuunganika
    moja kwa moja. Hii inazuia router "kurukwa" kimya kimya kwa sababu tu
    flag yake ya DB ilikuwa False wakati huo — bug hii ilikuwa ikisababisha
    vouchers nyingi (na hata clients wazima wenye router isiyoaminika)
    kutowahi kuonekana kwenye ripoti/notifications kabisa.
    """
    from apps.routers.models import MikroTikRouter
    from apps.routers.mikrotik import get_mikrotik_connection
    from apps.notifications.models import Notification
    from .models import Voucher

    now = timezone.now()

    pending_router_ids = list(
        Voucher.objects.filter(
            status='active', used_at__isnull=True, payment__isnull=True,
        ).values_list('router_id', flat=True).distinct()
    )
    routers = MikroTikRouter.objects.filter(id__in=pending_router_ids).select_related('client')

    total_found = 0
    routers_attempted = 0
    routers_failed = 0

    for router in routers:
        # MUHIMU: payment__isnull=True inahakikisha task hii inagusa TU
        # vouchers zilizoundwa kupitia manual/batch creation (VoucherManagementPage).
        # Vouchers za malipo ya moja kwa moja (zina Payment FK) zinashughulikiwa
        # na task tofauti iliyopo tayari: sync_voucher_status_from_mikrotik.
        # Hii inazuia mgongano/kazi mara mbili kati ya tasks hizi mbili.
        pending_codes = list(
            Voucher.objects.filter(
                router=router, status='active', used_at__isnull=True,
                payment__isnull=True,
            ).values_list('code', flat=True)
        )
        if not pending_codes:
            continue

        api = get_mikrotik_connection(router)
        routers_attempted += 1
        if not api:
            routers_failed += 1
            logger.warning(
                f"check_voucher_usage: imeshindwa kuunganika na {router.name} "
                f"(vouchers {len(pending_codes)} zinasubiri) — itajaribu tena mzunguko ujao"
            )
            continue

        try:
            schedulers = api.get_schedulers()
        except Exception as e:
            logger.error(f"check_voucher_usage: scheduler fetch imeshindwa {router.name}: {e}")
            continue
        finally:
            api.disconnect()

        # scheduler_by_name inashikilia row NZIMA (siyo jina tu), ili tupate
        # start-date/start-time — wakati HALISI voucher ilipoingizwa na
        # mteja, siyo wakati sisi tunapopiga poll.
        scheduler_by_name = {s.get('name', ''): s for s in schedulers}
        used_codes = [c for c in pending_codes if c in scheduler_by_name]
        if not used_codes:
            continue

        vouchers = Voucher.objects.filter(code__in=used_codes).select_related('package', 'client')
        for v in vouchers:
            sched = scheduler_by_name.get(v.code, {})
            real_used_at = _parse_mikrotik_datetime(
                sched.get('start-date', ''), sched.get('start-time', '')
            )
            # Ikiwa MikroTik format haikueleweka kwa sababu yoyote, tumia
            # wakati wa sasa kama salama badala ya kuvunja kabisa.
            v.used_at = real_used_at or now

            # ── MUHIMU (fix ya kufutwa mapema): sahihisha expires_at HAPA
            # kutoka wakati HALISI wa matumizi + muda wa package. Bila hii,
            # expires_at inabaki kwenye 'default ya usalama' iliyowekwa
            # wakati wa kuundwa (Voucher.save(): created_at + 2×duration) —
            # ambayo inaweza kuwa IMEPITA KABLA mteja hajaanza kutumia
            # voucher (mfano voucher ya siku 1 iliyoundwa siku 2 kabla ya
            # kutumika). expire_old_vouchers (kila saa) ingeifuta hotspot
            # user MAPEMA SANA, ingawa scheduler halisi (siku 1 kutoka
            # wakati wa kutumika) bado haijafika muda wake — ndicho
            # kilichokuwa kikitokea kwa vouchers za manual/batch.
            v.expires_at = v.used_at + timezone.timedelta(
                minutes=v.package.duration_minutes
            )
            v.save(update_fields=['used_at', 'expires_at'])

            if not v.usage_notified:
                try:
                    Notification.objects.create(
                        client=v.client,
                        title='Voucher imetumika',
                        message=(
                            f"Voucher {v.code} ({v.package.name}) imetumika na mteja — "
                            f"TZS {v.sold_price:,.0f}."
                        ),
                        level='success',
                        link='/client/analysis',
                    )
                except Exception as e:
                    logger.error(f"check_voucher_usage: notification imeshindwa kwa {v.code}: {e}")
                v.usage_notified = True
                v.save(update_fields=['usage_notified'])

        total_found += len(used_codes)

    logger.info(
        f"check_voucher_usage: routers zenye kazi {routers.count()}, "
        f"attempted {routers_attempted}, failed {routers_failed}, "
        f"vouchers zilizotambuliwa {total_found}"
    )


@shared_task
def generate_daily_sales_report():
    """
    Inakimbia saa 23:30 kila usiku (Celery Beat, Africa/Dar_es_Salaam).
    Kwa kila client, inahesabu vouchers zote zilizotumika (used_at) LEO,
    inahifadhi DailySalesReport, na kutuma Notification ya muhtasari.
    """
    from apps.clients.models import Client
    from apps.notifications.models import Notification
    from .models import Voucher, DailySalesReport

    today = timezone.localdate()
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(today, datetime.min.time()), tz)
    end = timezone.make_aware(datetime.combine(today, datetime.max.time()), tz)

    for client in Client.objects.filter(is_active=True):
        vouchers = Voucher.objects.filter(
            client=client, used_at__gte=start, used_at__lte=end
        ).select_related('package')

        total_count = vouchers.count()
        total_revenue = sum((v.sold_price for v in vouchers), Decimal('0'))

        breakdown_map = {}
        for v in vouchers:
            key = v.package.name if v.package_id else 'Bila jina'
            if key not in breakdown_map:
                breakdown_map[key] = {'package': key, 'count': 0, 'subtotal': Decimal('0')}
            breakdown_map[key]['count'] += 1
            breakdown_map[key]['subtotal'] += v.sold_price

        breakdown = [
            {
                'package': b['package'],
                'count': b['count'],
                'subtotal': float(b['subtotal']),
            }
            for b in breakdown_map.values()
        ]

        DailySalesReport.objects.update_or_create(
            client=client,
            date=today,
            defaults={
                'total_vouchers_sold': total_count,
                'total_revenue': total_revenue,
                'breakdown': breakdown,
            }
        )

        if total_count > 0:
            try:
                Notification.objects.create(
                    client=client,
                    title=f'Ripoti ya mauzo — {today.strftime("%d/%m/%Y")}',
                    message=(
                        f"Leo umeuza vocha {total_count} — jumla ya "
                        f"TZS {total_revenue:,.0f}."
                    ),
                    level='info',
                    link='/client/analysis',
                )
            except Exception as e:
                logger.error(f"generate_daily_sales_report: notification imeshindwa kwa {client.business_name}: {e}")

            # SMS kwa client (Africa's Talking, one-way) — nyongeza ya
            # notification ya in-app hapo juu. Njia huru, ya moja kwa moja —
            # haitumii wala haiathiri queue ya GSM (OutgoingSMS) kabisa.
            try:
                from apps.sms.at_service import send_at_sms
                send_at_sms(
                    client.phone,
                    f"NetSafi: Leo umeuza vocha {total_count} - jumla TZS {total_revenue:,.0f}."
                )
            except Exception as e:
                logger.error(f"generate_daily_sales_report: AT SMS imeshindwa kwa {client.business_name}: {e}")

        logger.info(
            f"Daily report {client.business_name}: vouchers {total_count}, "
            f"TZS {total_revenue}"
        )

=======
    logger.info(f"Expired {count} vouchers")
>>>>>>> ce77eb29d3fbe067206773bcdacb85bba7fb4c3c
