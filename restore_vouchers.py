import os
from decimal import Decimal
from datetime import datetime, date, timedelta, timezone as dt_tz
from django.utils import timezone
from apps.clients.models import Client
from apps.vouchers.models import Voucher, VoucherRouterPresence, DailySalesReport
from apps.routers.mikrotik import get_mikrotik_connection

DRY_RUN = os.environ.get('DRY_RUN', '1') != '0'
print("HALI:", "DRY-RUN (hakuna kinachobadilishwa)" if DRY_RUN else "LIVE (inabadilisha routers na database)")

MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
          'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}

def parse_sched_start(d, t):
    try:
        d = (d or '').strip().lower()
        if '-' in d:
            y, m, dd = (int(x) for x in d.split('-'))
        else:
            mon, dd, y = d.split('/')
            m = MONTHS[mon[:3]]
            dd = int(dd)
            y = int(y)
        hh, mi, ss = (int(x) for x in (t or '').strip().split(':'))
        return timezone.make_aware(datetime(y, m, dd, hh, mi, ss), timezone.get_current_timezone())
    except Exception:
        return None

now = timezone.now()
bug_start = datetime(2026, 9, 19, 3, 40, tzinfo=dt_tz.utc)
bug_end = datetime(2026, 9, 19, 4, 10, tzinfo=dt_tz.utc)
vouchers = list(Voucher.objects.filter(
    used_at__gte=bug_start, used_at__lte=bug_end
).select_related('router', 'package', 'client'))
print("Vouchers za kushughulikia:", len(vouchers))

cache = {}
def router_state(router):
    if router.id not in cache:
        st = None
        api = get_mikrotik_connection(router)
        if api:
            try:
                sched = {s.get('name'): s for s in api.command('/system/scheduler/print')}
                users = {u.get('name') for u in api.command('/ip/hotspot/user/print')}
                st = {'api': api, 'sched': sched, 'users': users, 'name': router.name}
            except Exception as e:
                print("Hitilafu kusoma", router.name, e)
                api.disconnect()
        else:
            print("OFFLINE:", router.name)
        cache[router.id] = st
    return cache[router.id]

def targets(v):
    rs = {v.router_id: v.router}
    for p in VoucherRouterPresence.objects.filter(voucher=v).select_related('router'):
        rs[p.router_id] = p.router
    return list(rs.values())

per_router = {}
def bump(name, key):
    per_router.setdefault(name, {}).setdefault(key, 0)
    per_router[name][key] += 1

def ensure_user(st, v, profile, comment):
    if v.code in st['users']:
        return True
    if DRY_RUN:
        bump(st['name'], 'ingeundwa')
        return True
    ok = st['api'].add_hotspot_user(username=v.code, password=v.code, profile=profile, comment=comment)
    if ok:
        st['users'].add(v.code)
        bump(st['name'], 'imeundwa')
    else:
        bump(st['name'], 'IMESHINDWA')
        print(f"  IMESHINDWA: {v.code} kwenye {st['name']} (profile={profile})")
    return ok

done_stock = []
done_used = []
skipped = 0
for v in vouchers:
    states = [(r, router_state(r)) for r in targets(v)]
    if any(st is None for r, st in states):
        skipped += 1
        continue
    profile = v.package.mikrotik_profile or 'default'
    comment = f"NetSafi|{v.client.business_name}|{v.customer_phone}"
    used_router = None
    used_row = None
    used_state = None
    for r, st in states:
        if v.code in st['sched']:
            used_router = r
            used_row = st['sched'][v.code]
            used_state = st
            break
    if used_row is None:
        results = [ensure_user(st, v, profile, comment) for r, st in states]
        if all(results):
            done_stock.append(v)
        else:
            skipped += 1
        continue
    real = parse_sched_start(used_row.get('start-date'), used_row.get('start-time'))
    if real is None:
        print(f"  ONYO: {v.code} tarehe ya scheduler haieleweki: {used_row.get('start-date')} {used_row.get('start-time')} -> imeruka")
        skipped += 1
        continue
    expires = real + timedelta(minutes=v.package.duration_minutes)
    valid = expires > now
    ok = True
    if valid:
        ok = ensure_user(used_state, v, profile, comment)
    if ok:
        done_used.append((v, used_router, real, expires, valid))
    else:
        skipped += 1

if not DRY_RUN:
    for v in done_stock:
        v.status = 'active'
        v.used_at = None
        v.expires_at = None
        v.sync_missing_since = None
        v.save(update_fields=['status', 'used_at', 'expires_at', 'sync_missing_since'])
        VoucherRouterPresence.objects.filter(voucher=v).update(status='active', removed_at=None)
    for v, r, real, expires, valid in done_used:
        v.used_at = real
        v.expires_at = expires
        v.router = r
        v.status = 'active' if valid else 'expired'
        v.sync_missing_since = None
        v.save(update_fields=['used_at', 'expires_at', 'router', 'status', 'sync_missing_since'])

print("\n--- Vouchers zilizotumika kweli (scheduler ipo) ---")
for v, r, real, expires, valid in done_used:
    print(f"{r.name:22} {v.code:10} ilitumika {real:%Y-%m-%d %H:%M} inaisha {expires:%Y-%m-%d %H:%M} {'BADO INAFAA' if valid else 'IMEISHA'}")

print("\n--- Muhtasari kwa router ---")
for name, c in per_router.items():
    print(f"{name:22} {c}")
print(f"\nStock (hazijatumika): {len(done_stock)} | Zilizotumika kweli: {len(done_used)} | Zilizorukwa: {skipped}")

if not DRY_RUN and skipped == 0:
    report_date = date(2026, 9, 19)
    tzc = timezone.get_current_timezone()
    r_start = timezone.make_aware(datetime.combine(report_date, datetime.min.time()), tzc)
    r_end = timezone.make_aware(datetime.combine(report_date, datetime.max.time()), tzc)
    print("\n--- Ripoti ya Sep 19 imejengwa upya ---")
    for client in Client.objects.filter(is_active=True):
        qs = Voucher.objects.filter(client=client, used_at__gte=r_start, used_at__lte=r_end).select_related('package')
        total_count = qs.count()
        total_revenue = sum((x.sold_price for x in qs), Decimal('0'))
        bm = {}
        for x in qs:
            key = x.package.name if x.package_id else 'Bila jina'
            b = bm.setdefault(key, {'package': key, 'count': 0, 'subtotal': Decimal('0')})
            b['count'] += 1
            b['subtotal'] += x.sold_price
        breakdown = [{'package': b['package'], 'count': b['count'], 'subtotal': float(b['subtotal'])} for b in bm.values()]
        DailySalesReport.objects.update_or_create(
            client=client, date=report_date,
            defaults={'total_vouchers_sold': total_count, 'total_revenue': total_revenue, 'breakdown': breakdown},
        )
        print(f"{client.business_name:22} vouchers={total_count:4} TZS {total_revenue}")
elif not DRY_RUN:
    print("\nRipoti HAIJAJENGWA kwa sababu kuna vouchers zilizorukwa. Iendeshe tena skripti routers zikiwa online.")

for st in cache.values():
    if st:
        st['api'].disconnect()
