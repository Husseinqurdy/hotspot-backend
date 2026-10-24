"""
Ufuatiliaji wa voucher — SOMA TU. Haibadilishi data yoyote.
  GET  /api/tracking/voucher/?code=XXXX   → ripoti kamili kutoka database (haraka)
  POST /api/tracking/voucher/live/        → uchunguzi wa moja kwa moja kwenye router (polepole, kwa ombi)
Superadmin anaona vouchers zote; client anaona zile za account yake (voucher yake au router yake) tu.
"""
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.routers.mikrotik import get_mikrotik_connection
from apps.routers.models import MikroTikJob
from apps.sms.models import OutgoingSMS
from apps.vouchers.models import Voucher

STUCK_AFTER = timedelta(minutes=10)


class IsStaffOrClient(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superadmin() or getattr(u, 'role', '') == 'client'))


def find_voucher(user, raw):
    code = (raw or '').strip()[:40]
    if not code:
        return None, code
    qs = Voucher.objects.select_related('client', 'router', 'package', 'payment', 'print_batch')
    if not user.is_superadmin():   # client: vouchers za account yake tu
        qs = qs.filter(Q(client__user=user) | Q(router__client__user=user))
    # jibu ni lile lile ikiwa voucher haipo au si ya client huyu — hakuna uvujaji wa taarifa
    return (qs.filter(code=code).first() or qs.filter(code__iexact=code).first()), code


def timeline(v, now):
    total = v.package.duration_minutes * 60
    out = {'created_at': v.created_at, 'first_used_at': v.used_at, 'expires_at': None,
           'total_seconds': total, 'remaining_seconds': None, 'elapsed_seconds': None}
    if v.used_at is None:
        out['state'] = 'expired' if v.status == 'expired' else 'unused'
        return out
    exp = v.expires_at or v.used_at + timedelta(seconds=total)
    rem = max(0, int((exp - now).total_seconds()))
    out.update(expires_at=exp, remaining_seconds=rem, elapsed_seconds=max(0, int((now - v.used_at).total_seconds())),
               state='expired' if (v.status == 'expired' or rem == 0) else 'running')
    return out


def build_issues(v, tl, payment, jobs, presences, sms, now):
    issues = []
    add = lambda code, level, **p: issues.append({'code': code, 'level': level, 'params': p})
    for j in jobs:
        if j['status'] == 'failed':
            add('job_failed', 'error', retries=j['retries'], error=(j['error_message'] or '')[:160])
        elif j['status'] in ('pending', 'processing') and now - j['created_at'] > STUCK_AFTER:
            add('job_stuck', 'warning', status=j['status'])
    if payment and payment['status'] != 'completed':
        add('payment_status', 'warning', status=payment['status'])
    if v.sync_missing_since:
        add('sync_missing', 'error', since=v.sync_missing_since.isoformat())
    if v.router and not v.router.is_online:
        add('router_offline', 'warning', router=v.router.name,
            last_seen=v.router.last_seen.isoformat() if v.router.last_seen else '')
    for p in presences:
        if p['status'] == 'failed':
            add('presence_failed', 'warning', router=p['router'], error=p['error_message'])
        elif p['status'] == 'removed':
            add('used_elsewhere', 'info', router=p['router'])
    if any(s['status'] == 'failed' for s in sms):
        add('sms_failed', 'warning')
    elif sms and all(s['status'] in ('queued', 'taken') and now - s['created_at'] > STUCK_AFTER for s in sms):
        add('sms_stuck', 'warning')
    if tl['state'] == 'expired':
        add('expired', 'info')
    elif tl['state'] == 'running' and tl['remaining_seconds'] is not None and tl['remaining_seconds'] < 1800:
        add('expires_soon', 'info', minutes=tl['remaining_seconds'] // 60)
    return issues


class VoucherLookupView(APIView):
    permission_classes = [IsStaffOrClient]

    def get(self, request):
        v, code = find_voucher(request.user, request.query_params.get('code'))
        if not code:
            return Response({'error': 'code_required'}, status=400)
        if not v:
            return Response({'error': 'not_found'}, status=404)
        now = timezone.now()
        tl = timeline(v, now)

        payment = None
        if v.payment_id:
            p = v.payment
            payment = {'amount': p.amount, 'transaction_id': p.transaction_id, 'network': p.network,
                       'status': p.status, 'phone': p.phone_number, 'created_at': p.created_at, 'processed_at': p.processed_at}

        jq = Q(voucher_code=v.code) | (Q(payment_id=v.payment_id) if v.payment_id else Q(pk__in=[]))
        jobs = [{'id': j.id, 'router': j.router.name, 'status': j.status, 'retries': j.retries,
                 'error_message': j.error_message, 'created_at': j.created_at, 'completed_at': j.completed_at}
                for j in MikroTikJob.objects.filter(jq).select_related('router').order_by('-created_at')[:10]]
        presences = [{'router': x.router.name, 'status': x.status, 'error_message': x.error_message,
                      'created_at': x.created_at, 'removed_at': x.removed_at}
                     for x in v.presences.select_related('router')]
        sms = [{'status': s.status, 'phone': s.phone, 'retries': s.retries, 'created_at': s.created_at, 'sent_at': s.sent_at}
               for s in OutgoingSMS.objects.filter(client=v.client, message__contains=v.code).order_by('-created_at')[:5]]

        return Response({
            'voucher': {'code': v.code, 'status': v.status, 'sold_price': v.sold_price, 'customer_phone': v.customer_phone,
                        'client': v.client.business_name, 'router': v.router.name if v.router_id else '',
                        'router_online': v.router.is_online if v.router_id else None,
                        'origin': 'payment' if v.payment_id else 'manual'},
            'package': {'name': v.package.name, 'duration_minutes': v.package.duration_minutes,
                        'speed_up': v.package.speed_up, 'speed_down': v.package.speed_down, 'profile': v.package.mikrotik_profile},
            'timeline': tl, 'payment': payment, 'jobs': jobs, 'presences': presences, 'sms': sms,
            'print_batch': ({'id': v.print_batch_id, 'created_at': v.print_batch.created_at, 'quantity': v.print_batch.quantity}
                            if v.print_batch_id else None),
            'issues': build_issues(v, tl, payment, jobs, presences, sms, now),
        })


class VoucherLiveView(APIView):
    """Inauliza router moja kwa moja — inaweza kuchukua hadi sekunde ~10 ikiwa router haijibu."""
    permission_classes = [IsStaffOrClient]

    def post(self, request):
        v, code = find_voucher(request.user, request.data.get('code'))
        if not code:
            return Response({'error': 'code_required'}, status=400)
        if not v or not v.router_id:
            return Response({'error': 'not_found'}, status=404)
        api = get_mikrotik_connection(v.router)
        if not api:
            return Response({'error': 'router_unreachable', 'router': v.router.name}, status=503)
        try:
            users = api.command('/ip/hotspot/user/print', queries={'name': v.code})
            active = api.command('/ip/hotspot/active/print', queries={'user': v.code})
            sched = api.command('/system/scheduler/print', queries={'name': v.code})
        except Exception as e:
            return Response({'error': 'router_error', 'detail': str(e)[:200]}, status=502)
        finally:
            api.disconnect()

        pick = lambda row, keys: {k: row.get(k, '') for k in keys} if row else None
        user = pick(users[0] if users else None, ['name', 'profile', 'uptime', 'limit-uptime', 'bytes-in', 'bytes-out', 'disabled', 'comment'])
        issues = []
        if not user:
            issues.append({'code': 'live_user_missing', 'level': 'info' if v.status == 'expired' else 'error', 'params': {}})
        elif user['disabled'] == 'true':
            issues.append({'code': 'live_disabled', 'level': 'error', 'params': {}})
        return Response({'router': v.router.name, 'user': user,
                         'active': pick(active[0] if active else None, ['address', 'mac-address', 'uptime', 'session-time-left']),
                         'scheduler': pick(sched[0] if sched else None, ['start-date', 'start-time', 'interval', 'next-run']),
                         'issues': issues})
