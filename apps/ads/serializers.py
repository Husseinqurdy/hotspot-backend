from rest_framework import serializers
from apps.routers.models import MikroTikRouter
from .models import Advertiser, Advertisement, AdImpression, SponsoredAccessLog


class AdvertiserSerializer(serializers.ModelSerializer):
    ads_count = serializers.SerializerMethodField()

    class Meta:
        model = Advertiser
        fields = [
            'id', 'name', 'contact_phone', 'contact_email',
            'is_active', 'created_at', 'updated_at', 'ads_count',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_ads_count(self, obj):
        return obj.ads.count()


class AdvertisementSerializer(serializers.ModelSerializer):
    advertiser_name = serializers.CharField(source='advertiser.name', read_only=True)
    router_ids = serializers.PrimaryKeyRelatedField(
        source='routers', many=True, required=False,
        queryset=MikroTikRouter.objects.select_related('client').all()
    )
    router_names = serializers.SerializerMethodField()
    is_currently_active = serializers.SerializerMethodField()

    class Meta:
        model = Advertisement
        fields = [
            'id', 'advertiser', 'advertiser_name', 'title', 'ad_type',
            'media_file', 'click_url', 'sponsored_minutes', 'cooldown_hours',
            'max_daily_grants_per_router', 'mikrotik_profile', 'start_date', 'end_date',
            'is_active', 'router_ids', 'router_names', 'priority', 'created_at',
            'updated_at', 'is_currently_active',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_router_names(self, obj):
        return [f"{r.name} ({r.client.business_name})" for r in obj.routers.all()]

    def get_is_currently_active(self, obj):
        return obj.is_currently_active()


class PublicAdSerializer(serializers.ModelSerializer):
    """
    Serializer nyepesi inayotumika na captive portal (endpoint ya public/active) -
    haionyeshi taarifa za ndani (advertiser contact, n.k.)
    """
    advertiser_name = serializers.CharField(source='advertiser.name', read_only=True)
    media_url = serializers.SerializerMethodField()

    class Meta:
        model = Advertisement
        fields = [
            'id', 'title', 'ad_type', 'media_url', 'click_url',
            'sponsored_minutes', 'advertiser_name',
        ]

    def get_media_url(self, obj):
        request = self.context.get('request')
        if obj.media_file and hasattr(obj.media_file, 'url'):
            url = obj.media_file.url
            if request:
                return request.build_absolute_uri(url)
            return url
        return None


class AdImpressionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdImpression
        fields = ['id', 'ad', 'router', 'client_mac', 'shown_at', 'clicked', 'clicked_at']
        read_only_fields = ['id', 'shown_at']


class SponsoredAccessLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SponsoredAccessLog
        fields = ['id', 'ad', 'router', 'client_mac', 'minutes_granted', 'granted_at', 'expires_at']
        read_only_fields = fields

