import logging

from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status as http_status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import GSMDevice
from .serializers import GSMDeviceSerializer, GSMDevicePublicSerializer

logger = logging.getLogger('netsafi')


class CheckinView(APIView):
    """
    Endpoint ya PUBLIC (hakuna auth) inayotumiwa na kifaa cha kimwili
    (ESP32) kujitangaza kwa mara ya kwanza, na kupiga tena mara kwa
    mara kusubiri kupewa api_key baada ya superadmin kukiclaim.

    HAKUNA api_key inayotumika hapa KWA MAKUSUDI — hii ndiyo hatua ya
    KWANZA kabisa ya uhusiano, kabla api_key haijazaliwa. Usalama
    unatokana na hili: factory_id peke yake haiwezi kutoa uwezo wa
    kusoma malipo ya mtu yeyote — inaweza tu kuunda rekodi TUPU ya
    'unclaimed' (angalia rate-limiting note chini).

    Body: {"factory_id": "<chip-id-ya-kipekee>"}
    Response ikiwa bado 'unclaimed': {"status": "unclaimed"}
    Response ikiwa tayari 'active': {"status": "active", "api_key": "..."}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        factory_id = request.data.get('factory_id', '').strip()
        if not factory_id:
            return Response({'error': 'factory_id inahitajika'}, status=400)

        # TODO (uzalishaji): ongeza rate-limiting hapa (mfano
        # django-ratelimit, max 5/dakika kwa IP) kuzuia spam ya
        # kuunda rekodi nyingi za 'unclaimed' zisizo za kweli.
        device, created = GSMDevice.objects.get_or_create(
            device_id=factory_id,
            defaults={'status': GSMDevice.STATUS_UNCLAIMED},
        )

        device.last_seen = timezone.now()
        device.save(update_fields=['last_seen'])

        if created:
            logger.info(f"Kifaa kipya kimejitangaza: factory_id={factory_id}")

        if device.status == GSMDevice.STATUS_UNCLAIMED or not device.api_key:
            return Response({'status': 'unclaimed'})

        return Response({'status': 'active', 'api_key': device.api_key})


class GSMDeviceViewSet(viewsets.ModelViewSet):
    serializer_class = GSMDeviceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = GSMDevice.objects.select_related('client').prefetch_related('shared_with')
        # Superadmin pekee anaona devices za clients WOTE (pamoja na
        # zile 'unclaimed' — hizi ni za superadmin peke yake kuona,
        # kwa sababu hazina client bado). Client wa kawaida anaona
        # vifaa anavyomiliki MWENYEWE, na vile alivyoongezwa kwenye
        # shared_with vya wengine.
        if user.is_superadmin():
            return qs
        client_profile = getattr(user, 'client_profile', None)
        if client_profile is None:
            return qs.none()
        return qs.filter(Q(client=client_profile) | Q(shared_with=client_profile)).distinct()

    @action(detail=False, methods=['get'], url_path='pending')
    def pending(self, request):
        """
        Orodha ya vifaa 'unclaimed' vinavyosubiri superadmin kuvi-claim
        — hii ndiyo 'portal' ya vifaa vipya (angalia mazungumzo kuhusu
        zero-touch provisioning).
        """
        if not request.user.is_superadmin():
            return Response(status=403)
        devices = GSMDevice.objects.filter(status=GSMDevice.STATUS_UNCLAIMED).order_by('-created_at')
        return Response(self.get_serializer(devices, many=True, context={'request': request}).data)

    def _resync_clients(self, client_ids):
        """
        Baada ya shared_with kubadilika (claim au update), packages
        za clients WOTE walioathirika (wa zamani na wapya, katika
        muungano) zinahitaji kuhesabu upya unique_amount yao — angalia
        Package.resync_unique_amount() na
        Client.requires_payment_identifier().
        """
        from apps.packages.models import Package
        for pkg in Package.objects.filter(client_id__in=client_ids).select_related('client'):
            pkg.resync_unique_amount()

    @action(detail=True, methods=['post'], url_path='claim')
    def claim(self, request, pk=None):
        """
        Superadmin anaweka client kwa kifaa cha 'unclaimed'. Baada ya
        hii, kifaa kitapata api_key yake kwenye checkin inayofuata.
        """
        if not request.user.is_superadmin():
            return Response(status=403)

        device = self.get_object()
        if device.status == GSMDevice.STATUS_ACTIVE:
            return Response({'error': 'Kifaa hiki tayari kime-claimed.'}, status=400)

        from apps.clients.models import Client
        client_id = request.data.get('client')
        name = request.data.get('name', '').strip()
        network = request.data.get('network', '').strip()
        lipa_number = request.data.get('lipa_number', '').strip()
        phone_number = request.data.get('phone_number', '').strip()
        shared_with_ids = request.data.get('shared_with', [])

        if not client_id or not name or not network or not lipa_number:
            return Response({'error': 'client, name, network na lipa_number zinahitajika'}, status=400)

        try:
            client = Client.objects.get(pk=client_id)
        except Client.DoesNotExist:
            return Response({'error': 'Client haipatikani'}, status=404)

        shared_with_qs = Client.objects.filter(id__in=shared_with_ids) if shared_with_ids else None

        device.claim(
            client=client, name=name, network=network,
            lipa_number=lipa_number, phone_number=phone_number,
            shared_with=shared_with_qs,
        )
        # Kifaa hiki kilikuwa 'unclaimed' (hakina client kabisa) kabla
        # ya hapa, kwa hiyo hakuna 'old' eligible_clients ya kuhangaika
        # nayo — tunahesabu upya TU kwa eligible_clients mpya.
        self._resync_clients([c.id for c in device.eligible_clients()])
        return Response(self.get_serializer(device, context={'request': request}).data)
    
    @action(detail=True, methods=['post'], url_path='command')
    def command(self, request, pk=None):
        """Superadmin/client anatuma amri ya remote kwa kifaa: 'restart' au 'sim_reset'."""
        if not request.user.is_superadmin():
            return Response(status=403)
        device = self.get_object()
        action_name = request.data.get('action')
        if action_name == 'restart':
            device.pending_restart = True
            device.save(update_fields=['pending_restart'])
        elif action_name == 'sim_reset':
            device.pending_sim_reset = True
            device.save(update_fields=['pending_sim_reset'])
        else:
            return Response({'error': "action lazima iwe 'restart' au 'sim_reset'"}, status=400)
        return Response({'message': f'Amri {action_name} imepangwa kwa {device.device_id}'})

    def create(self, request, *args, **kwargs):
        # Kuunda GSMDevice moja kwa moja (bila kupitia checkin/claim
        # flow) bado kunaruhusiwa — kwa mfano vifaa vinavyotambulika
        # kwa jina/QR bila kuwa vimewahi ku-checkin. Superadmin
        # anaweza kuunda kwa client yeyote; client wa kawaida
        # anaweza kuunda chake mwenyewe tu.
        user = request.user
        data = request.data.copy()
        if not user.is_superadmin():
            client_profile = getattr(user, 'client_profile', None)
            if client_profile is None:
                return Response({'error': 'Huna client profile'}, status=403)
            data['client'] = client_profile.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        out_serializer = self.get_serializer(instance, context={'request': request})
        headers = self.get_success_headers(out_serializer.data)
        # Kifaa kipya kilichoundwa moja kwa moja (siyo kupitia claim)
        # kinaweza kuja na shared_with tayari kwenye ombi la create —
        # hesabu upya papo hapo ili isisubiri kubadilika kwa mara ya
        # pili kupate unique_amount sahihi.
        self._resync_clients([c.id for c in instance.eligible_clients()])
        return Response(out_serializer.data, status=http_status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # MUHIMU: chukua 'picha' ya eligible_clients KABLA ya
        # mabadiliko — hii ndiyo njia pekee ya kujua ni nani
        # 'aliondolewa' kwenye sharing (mtu ambaye hataonekana tena
        # kwenye eligible_clients baada ya update, lakini bado
        # anahitaji packages zake kurudi kwenye bei flat).
        old_eligible_ids = {c.id for c in instance.eligible_clients()}

        user = request.user
        if not user.is_superadmin():
            client_profile = getattr(user, 'client_profile', None)
            if client_profile is None or instance.client_id != client_profile.id:
                return Response(status=403)
            data = request.data.copy()
            data.pop('client', None)
            partial = kwargs.get('partial', False)
            serializer = self.get_serializer(instance, data=data, partial=partial, context={'request': request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            response = Response(serializer.data)
        else:
            response = super().update(request, *args, **kwargs)

        # Instance ya awali inaweza kuwa na shared_with iliyo-cached
        # (prefetch_related kwenye get_queryset()) — tunachukua rekodi
        # MPYA kabisa kutoka DB badala ya kutegemea cache ya zamani.
        fresh = GSMDevice.objects.prefetch_related('shared_with').get(pk=instance.pk)
        new_eligible_ids = {c.id for c in fresh.eligible_clients()}
        self._resync_clients(old_eligible_ids | new_eligible_ids)
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user
        if not user.is_superadmin():
            client_profile = getattr(user, 'client_profile', None)
            if client_profile is None or instance.client_id != client_profile.id:
                return Response(status=403)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='regenerate-key')
    def regenerate_key(self, request, pk=None):
        instance = self.get_object()
        user = request.user
        if not user.is_superadmin():
            client_profile = getattr(user, 'client_profile', None)
            if client_profile is None or instance.client_id != client_profile.id:
                return Response(status=403)
        if not instance.api_key:
            return Response({'error': 'Kifaa hiki bado hakijaclaimwa'}, status=400)
        new_key = instance.regenerate_api_key()
        return Response({'api_key': new_key})

    @action(detail=False, methods=['get'], url_path='public')
    def public_list(self, request):
        """Lipa namba za client fulani, kwa umma. Inahitaji client_id."""
        client_id = request.query_params.get('client_id')
        if not client_id:
            return Response({'error': 'client_id inahitajika'}, status=400)
        devices = GSMDevice.objects.filter(
            Q(client_id=client_id) | Q(shared_with__id=client_id),
            is_active=True, status=GSMDevice.STATUS_ACTIVE,
        ).distinct().order_by('network')
        return Response(GSMDevicePublicSerializer(devices, many=True).data)
