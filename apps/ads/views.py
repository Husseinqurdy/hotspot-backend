import logging
from datetime import timedelta

from django.utils import timezone
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission

from apps.routers.models import MikroTikRouter
from apps.routers.mikrotik import get_mikrotik_connection
from .models import Advertiser, Advertisement, AdImpression, SponsoredAccessLog
from .serializers import (
    AdvertiserSerializer,
    AdvertisementSerializer,
    PublicAdSerializer,
    AdImpressionSerializer,
    SponsoredAccessLogSerializer,
)

logger = logging.getLogger('netsafi')


class IsSuperAdmin(BasePermission):
    """Ads ni mtandao mmoja unaosimamiwa na superadmin pekee - clients hawana access."""
    message = "Ni superadmin pekee anayeruhusiwa kusimamia matangazo."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superadmin()
        )


# =====================================================
# ADMIN / DASHBOARD ENDPOINTS (superadmin PEKEE)
# =====================================================

class AdvertiserViewSet(viewsets.ModelViewSet):
    serializer_class = AdvertiserSerializer
    permission_classes = [IsSuperAdmin]
    queryset = Advertiser.objects.all()


class AdvertisementViewSet(viewsets.ModelViewSet):
    serializer_class = AdvertisementSerializer
    permission_classes = [IsSuperAdmin]
    queryset = Advertisement.objects.select_related('advertiser').prefetch_related('routers')


# =====================================================
# PUBLIC ENDPOINTS (zinaitwa na captive portal - login.html
# ya client YEYOTE). Hakuna login inayohitajika.
# =====================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def active_ad(request):
    """
    GET /api/ads/active/?router_id=5
    Inarudisha ad yenye kipaumbele cha juu zaidi inayofaa kwa router hii
    (kutoka mtandao mzima wa ads - client wa router hii si muhimu hapa).
    """
    router_id = request.GET.get('router_id')
    if not router_id:
        return Response({"error": "router_id inahitajika"}, status=400)

    try:
        router = MikroTikRouter.objects.get(id=router_id)
    except MikroTikRouter.DoesNotExist:
        return Response({"error": "Router haipo"}, status=404)

    now = timezone.now()

    ads = Advertisement.objects.filter(
        is_active=True,
        start_date__lte=now,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=now)
    ).order_by('-priority', '-created_at')

    # Ad inaonekana kwenye router hii kama: haina router yoyote iliyowekwa
    # (yaani "zote"), AU router hii iko kwenye orodha yake maalum.
    matching = [
        ad for ad in ads
        if (not ad.routers.exists()) or ad.routers.filter(id=router.id).exists()
    ]

    if not matching:
        return Response({"ad": None})

    ad = matching[0]
    serializer = PublicAdSerializer(ad, context={'request': request})
    return Response({"ad": serializer.data})


@api_view(['POST'])
@permission_classes([AllowAny])
def record_impression(request):
    """POST /api/ads/impression/  body: {ad_id, router_id, client_mac}"""
    ad_id = request.data.get('ad_id')
    router_id = request.data.get('router_id')
    client_mac = request.data.get('client_mac', '')

    if not ad_id or not router_id:
        return Response({"error": "ad_id na router_id vinahitajika"}, status=400)

    impression = AdImpression.objects.create(
        ad_id=ad_id, router_id=router_id, client_mac=client_mac
    )
    return Response({"id": impression.id, "status": "recorded"}, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
def record_click(request):
    """POST /api/ads/click/  body: {impression_id}"""
    impression_id = request.data.get('impression_id')

    if impression_id:
        try:
            impression = AdImpression.objects.get(id=impression_id)
            impression.clicked = True
            impression.clicked_at = timezone.now()
            impression.save(update_fields=['clicked', 'clicked_at'])
            return Response({"status": "recorded"})
        except AdImpression.DoesNotExist:
            pass

    return Response({"error": "impression_id sahihi inahitajika"}, status=400)


def _sponsored_username(client_mac):
    """Jina thabiti la hotspot user kwa MAC fulani - MAC hii hii itatumia
    jina hili hili kila wakati inapopata sponsored access mpya."""
    return 'SP-' + client_mac.replace(':', '').replace('-', '').upper()


def _grant_mikrotik_sponsored_session(router, client_mac, minutes, profile='sponsored_free'):
    """
    Tengeneza hotspot user wa muda kwenye MikroTik yenye 'limit-uptime'
    sawa na dakika za ad hii. Username ni thabiti kwa MAC.

    MUHIMU: 'profile' LAZIMA iwe profile iliyotengenezwa tayari kwenye
    router hii (rate-limit ya chini kuliko packages za kulipia).
    """
    api = get_mikrotik_connection(router)
    if not api:
        logger.warning(f"_grant_mikrotik_sponsored_session: router {router.name} haipo online")
        return False

    username = _sponsored_username(client_mac)

    try:
        try:
            api.delete_hotspot_user(username)
        except Exception:
            pass

        api.command('/ip/hotspot/user/add', {
            'name': username,
            'password': username,
            'profile': profile,
            'limit-uptime': f'{minutes}m',
            'mac-address': client_mac,
            'comment': f'SPONSORED|{minutes}min',
        })
        return True
    except Exception as e:
        logger.error(f"_grant_mikrotik_sponsored_session error kwa {client_mac}: {e}")
        return False
    finally:
        api.disconnect()


@api_view(['POST'])
@permission_classes([AllowAny])
def grant_sponsored_access(request):
    """
    POST /api/ads/grant-sponsored/
    body: {ad_id, router_id, client_mac}
    """
    ad_id = request.data.get('ad_id')
    router_id = request.data.get('router_id')
    client_mac = request.data.get('client_mac')

    if not all([ad_id, router_id, client_mac]):
        return Response({"error": "ad_id, router_id, client_mac vinahitajika"}, status=400)

    try:
        ad = Advertisement.objects.get(id=ad_id, ad_type=Advertisement.AD_TYPE_SPONSORED)
    except Advertisement.DoesNotExist:
        return Response({"error": "Ad ya sponsored_access haipatikani"}, status=404)

    try:
        router = MikroTikRouter.objects.get(id=router_id)
    except MikroTikRouter.DoesNotExist:
        return Response({"error": "Router haipo"}, status=404)

    if not ad.is_currently_active():
        return Response({"allowed": False, "message": "Tangazo hili halipatikani kwa sasa."}, status=410)

    recent = SponsoredAccessLog.objects.filter(
        client_mac=client_mac,
        router=router,
        ad=ad,
        granted_at__gte=timezone.now() - timedelta(hours=ad.cooldown_hours)
    ).exists()

    if recent:
        return Response({
            "allowed": False,
            "message": f"Umeshapata dakika za bure. Jaribu tena baada ya masaa {ad.cooldown_hours}, au weka vocha.",
        }, status=429)

    if ad.max_daily_grants_per_router > 0:
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = SponsoredAccessLog.objects.filter(
            router=router, ad=ad, granted_at__gte=today_start
        ).count()

        if today_count >= ad.max_daily_grants_per_router:
            return Response({
                "allowed": False,
                "message": "Sponsored access ya leo imeisha kwa router hii. Weka vocha badala yake.",
            }, status=429)

    ok = _grant_mikrotik_sponsored_session(
        router, client_mac, ad.sponsored_minutes, profile=ad.mikrotik_profile
    )

    if not ok:
        return Response({"allowed": False, "message": "Imeshindikana kuunganisha na router. Jaribu tena."}, status=502)

    SponsoredAccessLog.objects.create(
        ad=ad,
        router=router,
        client_mac=client_mac,
        minutes_granted=ad.sponsored_minutes,
        expires_at=timezone.now() + timedelta(hours=ad.cooldown_hours),
    )

    return Response({"allowed": True, "minutes": ad.sponsored_minutes})


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def ad_report(request):
    """GET /api/ads/report/?router_id=5&ad_id=3  -> muhtasari wa impressions/clicks/grants (superadmin pekee)"""
    router_id = request.GET.get('router_id')
    ad_id = request.GET.get('ad_id')

    impressions = AdImpression.objects.all()
    grants = SponsoredAccessLog.objects.all()

    if router_id:
        impressions = impressions.filter(router_id=router_id)
        grants = grants.filter(router_id=router_id)
    if ad_id:
        impressions = impressions.filter(ad_id=ad_id)
        grants = grants.filter(ad_id=ad_id)

    total_impressions = impressions.count()
    total_clicks = impressions.filter(clicked=True).count()
    total_sponsored_grants = grants.count()
    ctr = round((total_clicks / total_impressions) * 100, 2) if total_impressions else 0

    return Response({
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "click_through_rate_percent": ctr,
        "total_sponsored_grants": total_sponsored_grants,
    })

