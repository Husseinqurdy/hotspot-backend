import logging
import re
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Package
from .serializers import PackageSerializer

logger = logging.getLogger('hotspot')


class PackageViewSet(viewsets.ModelViewSet):
    serializer_class = PackageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = (
            Package.objects.select_related('client').all()
            if self.request.user.is_superadmin()
            else Package.objects.filter(client__user=self.request.user)
        )
        if cid := self.request.query_params.get('client'):
            qs = qs.filter(client_id=cid)
        return qs

    def perform_create(self, serializer):
        if self.request.user.is_client():
            from apps.clients.models import Client
            serializer.save(client=Client.objects.get(user=self.request.user))
        else:
            serializer.save()


# ══════════════════════════════════════════════════════════════
# SYNC: Soma profile kutoka MikroTik → sasisha Package kwenye DB
# ══════════════════════════════════════════════════════════════

class SyncPackageFromMikroTikView(APIView):
    """
    POST /api/packages/<package_id>/sync-from-mikrotik/

    Inasoma hotspot profile ya package kutoka MikroTik router
    na kusasisha Package model kwenye database — bila kubadilisha MikroTik.

    Fields zinazosasishwa:
      - shared_users  ← profile['shared-users']
      - speed_up      ← rate-limit (e.g. "5M/2M" → speed_up=5)
      - speed_down    ← rate-limit (e.g. "5M/2M" → speed_down=2)
      - duration_value + duration_unit ← session-timeout (e.g. "2h" → 2 hours)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, package_id):
        # ── 1. Pata package ───────────────────────────────────────
        try:
            if request.user.is_superadmin():
                package = Package.objects.select_related('client').get(pk=package_id)
            else:
                package = Package.objects.select_related('client').get(
                    pk=package_id, client__user=request.user
                )
        except Package.DoesNotExist:
            return Response({'error': 'Package haikupatikana'}, status=404)

        # ── 2. Pata router ya kwanza online ya client ─────────────
        from apps.routers.models import MikroTikRouter
        from apps.routers.mikrotik import get_mikrotik_connection

        router = MikroTikRouter.objects.filter(
            client=package.client, is_online=True
        ).first()

        if not router:
            return Response(
                {'error': f'Hakuna router online ya {package.client.business_name}'},
                status=503
            )

        # ── 3. Unganika na MikroTik ───────────────────────────────
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Haiwezekani kuunganika na router'}, status=503)

        try:
            profiles = api.command(
                '/ip/hotspot/user/profile/print',
                queries={'name': package.mikrotik_profile}
            )
        except Exception as e:
            logger.error(f"SyncPackage: command failed: {e}")
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

        if not profiles:
            return Response(
                {'error': f"Profile '{package.mikrotik_profile}' haikupatikana kwenye MikroTik"},
                status=404
            )

        profile = profiles[0]
        changes = {}

        # ── 4. Linganisha na sasisha ──────────────────────────────

        # shared-users
        mt_shared = _parse_int(profile.get('shared-users'), default=1)
        if mt_shared != package.shared_users:
            changes['shared_users'] = {'before': package.shared_users, 'after': mt_shared}
            package.shared_users = mt_shared

        # rate-limit → speed_up / speed_down
        rate_limit = profile.get('rate-limit', '')
        if rate_limit:
            up, down = _parse_rate_limit(rate_limit)
            if up and up != package.speed_up:
                changes['speed_up'] = {'before': package.speed_up, 'after': up}
                package.speed_up = up
            if down and down != package.speed_down:
                changes['speed_down'] = {'before': package.speed_down, 'after': down}
                package.speed_down = down

        # session-timeout → duration_value + duration_unit
        session_timeout = profile.get('session-timeout', '')
        if session_timeout:
            val, unit = _parse_session_timeout(session_timeout)
            if val and unit:
                if val != package.duration_value or unit != package.duration_unit:
                    changes['duration'] = {
                        'before': f"{package.duration_value} {package.duration_unit}",
                        'after':  f"{val} {unit}",
                    }
                    package.duration_value = val
                    package.duration_unit  = unit

        # ── 5. Hifadhi kama kuna mabadiliko ──────────────────────
        if changes:
            update_fields = ['duration_minutes']
            if 'shared_users' in changes:
                update_fields.append('shared_users')
            if 'speed_up' in changes:
                update_fields.append('speed_up')
            if 'speed_down' in changes:
                update_fields.append('speed_down')
            if 'duration' in changes:
                update_fields += ['duration_value', 'duration_unit']

            package.duration_minutes = package._compute_duration_minutes()

            # Tumia .update() — epuka kuita _sync_to_mikrotik tena
            Package.objects.filter(pk=package.pk).update(
                **{f: getattr(package, f) for f in update_fields}
            )

            logger.info(f"SyncPackage: '{package.name}' imesasishwa. Mabadiliko: {changes}")
            return Response({
                'synced':  True,
                'changes': changes,
                'message': f"Package '{package.name}' imesasishwa kutoka MikroTik ✓",
            })
        else:
            return Response({
                'synced':  False,
                'changes': {},
                'message': f"Package '{package.name}' iko sawa — hakuna mabadiliko",
            })


# ══════════════════════════════════════════════════════════════
# SYNC ALL: Sync packages zote za client mara moja
# ══════════════════════════════════════════════════════════════

class SyncAllPackagesFromMikroTikView(APIView):
    """
    POST /api/packages/sync-all-from-mikrotik/
    Query param: ?client=<client_id>  (inahitajika kwa superadmin)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.routers.models import MikroTikRouter
        from apps.routers.mikrotik import get_mikrotik_connection

        if request.user.is_superadmin():
            client_id = request.query_params.get('client') or request.data.get('client')
            if not client_id:
                return Response({'error': 'client id inahitajika'}, status=400)
            packages = Package.objects.filter(client_id=client_id)
        else:
            packages = Package.objects.filter(client__user=request.user)

        if not packages.exists():
            return Response({'error': 'Hakuna packages'}, status=404)

        client = packages.first().client

        router = MikroTikRouter.objects.filter(client=client, is_online=True).first()
        if not router:
            return Response(
                {'error': f'Hakuna router online ya {client.business_name}'},
                status=503
            )

        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Haiwezekani kuunganika na router'}, status=503)

        try:
            # Soma profiles ZOTE mara moja — haraka zaidi
            all_profiles = api.command('/ip/hotspot/user/profile/print')
            profiles_map = {p['name']: p for p in all_profiles if 'name' in p}
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

        results = []
        synced_count = 0

        for pkg in packages:
            profile = profiles_map.get(pkg.mikrotik_profile)
            if not profile:
                results.append({
                    'package': pkg.name,
                    'synced': False,
                    'reason': f"Profile '{pkg.mikrotik_profile}' haikupatikana kwenye MikroTik",
                })
                continue

            changes = {}
            update_fields = []

            # shared-users
            mt_shared = _parse_int(profile.get('shared-users'), default=1)
            if mt_shared != pkg.shared_users:
                changes['shared_users'] = {'before': pkg.shared_users, 'after': mt_shared}
                pkg.shared_users = mt_shared
                update_fields.append('shared_users')

            # rate-limit
            rate_limit = profile.get('rate-limit', '')
            if rate_limit:
                up, down = _parse_rate_limit(rate_limit)
                if up and up != pkg.speed_up:
                    changes['speed_up'] = {'before': pkg.speed_up, 'after': up}
                    pkg.speed_up = up
                    update_fields.append('speed_up')
                if down and down != pkg.speed_down:
                    changes['speed_down'] = {'before': pkg.speed_down, 'after': down}
                    pkg.speed_down = down
                    update_fields.append('speed_down')

            # session-timeout
            session_timeout = profile.get('session-timeout', '')
            if session_timeout:
                val, unit = _parse_session_timeout(session_timeout)
                if val and unit:
                    if val != pkg.duration_value or unit != pkg.duration_unit:
                        changes['duration'] = {
                            'before': f"{pkg.duration_value} {pkg.duration_unit}",
                            'after':  f"{val} {unit}",
                        }
                        pkg.duration_value = val
                        pkg.duration_unit  = unit
                        update_fields += ['duration_value', 'duration_unit']

            if changes:
                pkg.duration_minutes = pkg._compute_duration_minutes()
                update_fields.append('duration_minutes')
                Package.objects.filter(pk=pkg.pk).update(
                    **{f: getattr(pkg, f) for f in update_fields}
                )
                synced_count += 1
                results.append({'package': pkg.name, 'synced': True, 'changes': changes})
            else:
                results.append({'package': pkg.name, 'synced': False, 'changes': {}})

        return Response({
            'total':   packages.count(),
            'synced':  synced_count,
            'results': results,
            'message': f"{synced_count} package(s) zimesasishwa kutoka MikroTik ✓",
        })


# ══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════

def _parse_int(value, default=1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_rate_limit(rate_limit: str):
    """
    Geuza rate-limit string ya MikroTik kuwa (speed_up, speed_down).
    Mifano:
      "5M/2M"        → ("5", "2")
      "10M/10M"      → ("10", "10")
      "512k/256k"    → ("0.5", "0.25")
      "5M/2M 10M/5M" → ("5", "2")  ← CIR tu
    """
    if not rate_limit:
        return None, None
    try:
        part = rate_limit.strip().split()[0]
        if '/' not in part:
            return None, None
        up_str, down_str = part.split('/', 1)

        def to_mbps(s):
            s = s.strip().upper()
            if s.endswith('M'):
                val = float(s[:-1])
                return str(int(val)) if val == int(val) else str(val)
            elif s.endswith('K'):
                val = float(s[:-1]) / 1024
                return str(round(val, 2))
            elif s.endswith('G'):
                val = float(s[:-1]) * 1024
                return str(int(val))
            else:
                return s

        return to_mbps(up_str), to_mbps(down_str)
    except Exception as e:
        logger.warning(f"_parse_rate_limit failed for '{rate_limit}': {e}")
        return None, None


def _parse_session_timeout(timeout: str):
    """
    Geuza session-timeout string ya MikroTik kuwa (value, unit).
    Mifano:
      "1h"           → (1, "hours")
      "2h"           → (2, "hours")
      "24h"          → (1, "days")
      "1d 00:00:00"  → (1, "days")
      "2d 00:00:00"  → (2, "days")
    """
    if not timeout:
        return None, None
    try:
        timeout = timeout.strip().lower()

        day_match = re.match(r'^(\d+)d', timeout)
        if day_match:
            return int(day_match.group(1)), 'days'

        hour_match = re.match(r'^(\d+)h', timeout)
        if hour_match:
            hours = int(hour_match.group(1))
            if hours >= 24 and hours % 24 == 0:
                return hours // 24, 'days'
            return hours, 'hours'

        time_match = re.match(r'^(\d+):(\d+):(\d+)$', timeout)
        if time_match:
            h = int(time_match.group(1))
            m = int(time_match.group(2))
            if h > 0 and m == 0:
                if h >= 24 and h % 24 == 0:
                    return h // 24, 'days'
                return h, 'hours'

        return None, None
    except Exception as e:
        logger.warning(f"_parse_session_timeout failed for '{timeout}': {e}")
        return None, None
