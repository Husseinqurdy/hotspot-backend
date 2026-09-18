import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from .models import MikroTikRouter
from .mikrotik import get_mikrotik_connection

logger = logging.getLogger('netsafi')


def get_router_for_user(router_id, user):
    """Pata router na angalia ruhusa."""
    try:
        if user.is_superadmin():
            return MikroTikRouter.objects.get(id=router_id)
        else:
            return MikroTikRouter.objects.get(id=router_id, client__user=user)
    except MikroTikRouter.DoesNotExist:
        return None


class RouterStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            router.is_online = False
            router.save(update_fields=['is_online'])
            return Response({'error': 'Router haipo online', 'is_online': False}, status=503)
        try:
            resource = api.get_resource()
            routerboard = api.get_routerboard()
            identity = api.get_identity()
            router.is_online = True
            router.last_seen = timezone.now()
            router.save(update_fields=['is_online', 'last_seen'])
            return Response({
                'is_online': True,
                'identity': identity,
                'resource': {
                    'cpu_load': resource.get('cpu-load', '0') + '%',
                    'free_memory': resource.get('free-memory', '0'),
                    'total_memory': resource.get('total-memory', '0'),
                    'uptime': resource.get('uptime', '0'),
                    'version': resource.get('version', ''),
                    'board_name': resource.get('board-name', ''),
                    'architecture': resource.get('architecture-name', ''),
                    'free_hdd': resource.get('free-hdd-space', '0'),
                    'total_hdd': resource.get('total-hdd-space', '0'),
                },
                'routerboard': {
                    'model': routerboard.get('model', ''),
                    'serial': routerboard.get('serial-number', ''),
                    'firmware': routerboard.get('current-firmware', ''),
                },
            })
        except Exception as e:
            logger.error(f"Router status error: {e}")
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class RouterInterfacesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            interfaces = api.get_interfaces()
            return Response({'interfaces': interfaces, 'count': len(interfaces)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class RouterIPAddressesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            addresses = api.get_ip_addresses()
            routes = api.get_routes()
            return Response({'addresses': addresses, 'routes': routes})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class HotspotUsersView(APIView):
    """Hotspot users — ona, ongeza, hariri, futa."""
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            users = api.get_hotspot_users()
            return Response({'users': users, 'count': len(users)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def post(self, request, router_id):
<<<<<<< HEAD
        """Ongeza hotspot user mpya + rekodi Voucher kwa historia/ripoti.

        MUHIMU: kama 'username' iliyotumwa tayari ipo (kwenye MikroTik ya
        router hii, AU kwenye Voucher table kimataifa — Voucher.code ni
        unique kimataifa, siyo per-router), tunatengeneza code MPYA
        moja kwa moja na kujaribu tena (mpaka mara 8), badala ya
        kushindwa moja kwa moja. Hii inazuia batch creation (mfano
        vouchers 100) kupoteza asilimia kubwa kwa sababu ya migongano
        ya nasibu ya code — na inazuia pia hitilafu kubwa zaidi
        iliyofichika: code inayogongana na client MWINGINE (router
        tofauti) ingeweza kuandika upya voucher ya mtu mwingine kimya
        kimya kupitia update_or_create.

        Response sasa inarudisha 'code' HALISI iliyotumika (inaweza
        kuwa tofauti na 'username' ulioomba awali) — frontend LAZIMA
        itumie hii kwa ajili ya print card / SMS / orodha, siyo ile
        iliyotuma.
        """
=======
        """Ongeza hotspot user mpya."""
>>>>>>> ce77eb29d3fbe067206773bcdacb85bba7fb4c3c
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
<<<<<<< HEAD
            requested_username = request.data.get('username', '')
            profile = request.data.get('profile', 'default')
            comment = request.data.get('comment', 'Manual')
            if not requested_username:
                return Response({'error': 'username inahitajika'}, status=400)

            final_code = self._find_unique_code(api, requested_username)
            if final_code is None:
                return Response(
                    {'error': 'Imeshindwa kupata code ya kipekee baada ya majaribio kadhaa — jaribu tena'},
                    status=409
                )

            # Password ya voucher daima ni sawa na code yake (ndivyo
            # frontend inavyotuma kila mara: username == password).
            success = api.add_hotspot_user(final_code, final_code, profile, comment)
            if not success:
                return Response({'error': 'Imeshindwa kuongeza user'}, status=400)

            # ── rekodi Voucher kwa historia + ripoti ya mauzo ──────
            # Hii haiathiri flow ya MikroTik iliyo juu. Ikishindwa kwa sababu
            # yoyote, voucher bado inafanya kazi kwenye hotspot — tunaandika
            # logi ya onyo badala ya kuvunja request nzima.
            self._record_voucher(router, final_code, profile, comment)

            return Response({'message': f'User {final_code} ameongezwa', 'code': final_code})
=======
            username = request.data.get('username', '')
            password = request.data.get('password', username)
            profile  = request.data.get('profile', 'default')
            comment  = request.data.get('comment', 'Manual')
            if not username:
                return Response({'error': 'username inahitajika'}, status=400)
            success = api.add_hotspot_user(username, password, profile, comment)
            if success:
                return Response({'message': f'User {username} ameongezwa'})
            return Response({'error': 'Imeshindwa kuongeza user'}, status=400)
>>>>>>> ce77eb29d3fbe067206773bcdacb85bba7fb4c3c
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

<<<<<<< HEAD
    def _find_unique_code(self, api, preferred_code, max_attempts=8):
        """
        Rudisha code ya kipekee inayoweza kutumika salama — kwanza
        jaribu 'preferred_code' iliyoombwa; ikigongana (kwenye MikroTik
        ya router hii AU kwenye Voucher table kimataifa), tengeneza
        mbadala wenye urefu ule ule na jaribu tena. Rudisha None kama
        imeshindikana baada ya majaribio yote.
        """
        import random
        from apps.vouchers.models import Voucher

        chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
        length = len(preferred_code) or 8
        candidate = preferred_code

        for _ in range(max_attempts):
            exists_on_router = bool(api.command(
                '/ip/hotspot/user/print', queries={'name': candidate}
            ))
            exists_in_db = Voucher.objects.filter(code=candidate).exists()

            if not exists_on_router and not exists_in_db:
                return candidate

            candidate = ''.join(random.choices(chars, k=length))

        return None

    def _record_voucher(self, router, code, profile, comment):
        """Tafuta Package kwa profile, kisha unda/sasisha Voucher DB record."""
        from apps.packages.models import Package
        from apps.vouchers.models import Voucher

        try:
            package = Package.objects.filter(
                client=router.client, mikrotik_profile=profile
            ).first()

            if not package:
                logger.warning(
                    f"_record_voucher: Package haikupatikana kwa profile "
                    f"'{profile}' (client={router.client_id}) — voucher {code} "
                    f"itafanya kazi kwenye hotspot lakini haitaonekana kwenye "
                    f"historia/ripoti ya mauzo."
                )
                return

            # Comment za frontend ni: "Manual|0744123456" au "Batch|11/07/2026"
            phone = ''
            if comment and comment.startswith('Manual|'):
                candidate = comment.split('|', 1)[1].strip()
                if candidate and candidate != 'N/A':
                    phone = candidate

            Voucher.objects.update_or_create(
                code=code,
                defaults={
                    'client': router.client,
                    'router': router,
                    'package': package,
                    'customer_phone': phone,
                    'sold_price': package.price,
                }
            )
        except Exception as e:
            logger.error(f"_record_voucher error kwa {code}: {e}")

=======
>>>>>>> ce77eb29d3fbe067206773bcdacb85bba7fb4c3c
    def patch(self, request, router_id):
        """
        Hariri hotspot user iliyopo.
        Frontend inatuma: { username, password, profile, comment,
                            limit-uptime, limit-bytes-in, limit-bytes-out,
                            limit-bytes-total, mac-address, address, disabled }
        """
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)

        username = request.data.get('username')
        if not username:
            return Response({'error': 'username inahitajika'}, status=400)

        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)

        try:
            # Fields zinazoweza kubadilishwa — zote ni optional
            # Jina la field katika MikroTik ni sawa na linaloletwa na frontend
            # isipokuwa 'address' (frontend) = 'address' (MT) — sawa
            allowed_fields = [
                'password',
                'profile',
                'comment',
                'limit-uptime',
                'limit-bytes-in',
                'limit-bytes-out',
                'limit-bytes-total',
                'mac-address',
                'address',
                'disabled',
            ]
            params = {'username': username}
            for field in allowed_fields:
                if field in request.data:
                    params[field] = request.data[field]

            if len(params) == 1:
                # Hakuna kitu kingine zaidi ya username
                return Response({'error': 'Hakuna fields za kusasisha'}, status=400)

            success = api.edit_hotspot_user(params)
            if success:
                return Response({'message': f'User {username} imesasishwa'})
            return Response({'error': 'Imeshindwa kusasisha user'}, status=400)
        except Exception as e:
            logger.error(f"Patch hotspot user error: {e}")
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class HotspotUserDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, router_id):
        username = request.data.get('username')
        if not username:
            return Response({'error': 'username inahitajika'}, status=400)
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            success = api.delete_hotspot_user(username)
            if success:
                return Response({'message': f'User {username} amefutwa'})
            return Response({'error': 'Imeshindwa kufuta user'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class HotspotActiveSessionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            sessions = api.get_active_sessions()
            return Response({'sessions': sessions, 'count': len(sessions)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def delete(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'error': 'session_id inahitajika'}, status=400)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            success = api.disconnect_session(session_id)
            return Response({'message': 'Session imekatwa' if success else 'Imeshindwa'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class HotspotProfilesView(APIView):
    """
    Hotspot profiles — ona na hariri.
    GET  → orodha ya profiles zote
    PATCH → sasisha profile iliyopo
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            profiles = api.get_hotspot_profiles()
            return Response({'profiles': profiles})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def patch(self, request, router_id):
        """
        Hariri hotspot profile iliyopo.
        Frontend inatuma: { profile_name, name, rate-limit, session-timeout,
                            idle-timeout, keepalive-timeout, shared-users,
                            dns-name, html-directory, http-cookie-lifetime,
                            status-autorefresh, address-pool, mac-cookie-timeout,
                            on-login, on-logout }
        """
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)

        profile_name = request.data.get('profile_name')
        if not profile_name:
            return Response({'error': 'profile_name inahitajika'}, status=400)

        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)

        try:
            # Fields zote zinazoweza kubadilishwa kwa hotspot profile
            allowed_fields = [
                'name',
                'rate-limit',
                'session-timeout',
                'idle-timeout',
                'keepalive-timeout',
                'shared-users',
                'dns-name',
                'html-directory',
                'http-cookie-lifetime',
                'status-autorefresh',
                'transparent-proxy',
                'address-pool',
                'mac-cookie-timeout',
                'on-login',
                'on-logout',
            ]
            params = {'profile_name': profile_name}
            for field in allowed_fields:
                if field in request.data:
                    params[field] = request.data[field]

            if len(params) == 1:
                return Response({'error': 'Hakuna fields za kusasisha'}, status=400)

            success = api.edit_hotspot_profile(params)
            if success:
                return Response({'message': f'Profile "{profile_name}" imesasishwa'})
            return Response({'error': 'Imeshindwa kusasisha profile'}, status=400)
        except Exception as e:
            logger.error(f"Patch hotspot profile error: {e}")
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class RouterRestartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            api.restart()
            router.is_online = False
            router.save(update_fields=['is_online'])
            return Response({'message': 'Router inaanzisha upya... Subiri dakika 1-2'})
        except Exception as e:
            return Response({'message': 'Router inaanzisha upya...'})
        finally:
            try:
                api.disconnect()
            except:
                pass


class BandwidthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            interfaces = api.get_interfaces()
            traffic_data = []
            for iface in interfaces[:5]:
                name = iface.get('name', '')
                if name:
                    traffic = api.get_interface_traffic(name)
                    traffic_data.append({
                        'interface': name,
                        'type': iface.get('type', ''),
                        'running': iface.get('running', 'false'),
                        'tx_byte': iface.get('tx-byte', '0'),
                        'rx_byte': iface.get('rx-byte', '0'),
                        'traffic': traffic[0] if traffic else {}
                    })
            return Response({'traffic': traffic_data})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class RouterFirewallView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            filter_rules = api.get_firewall_rules()
            nat_rules = api.get_nat_rules()
            return Response({'filter_rules': filter_rules, 'nat_rules': nat_rules})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class RouterLogsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            logs = api.get_logs(limit=100)
            return Response({'logs': logs, 'count': len(logs)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class RouterDNSView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            dns = api.get_dns()
            return Response({'dns': dns})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class HotspotServersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            servers = api.get_hotspot_servers()
            return Response({'servers': servers, 'count': len(servers)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class HotspotHostsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            hosts = api.get_hotspot_hosts()
            return Response({'hosts': hosts, 'count': len(hosts)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class IPBindingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            bindings = api.get_ip_bindings()
            return Response({'bindings': bindings, 'count': len(bindings)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def post(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            mac    = request.data.get('mac_address', '')
            ip     = request.data.get('ip_address', '')
            btype  = request.data.get('type', 'regular')
            comment = request.data.get('comment', '')
            if not mac:
                return Response({'error': 'mac_address inahitajika'}, status=400)
            success = api.add_ip_binding(mac, ip, btype, comment)
            if success:
                return Response({'message': 'IP Binding imeongezwa'})
            return Response({'error': 'Imeshindwa kuongeza binding'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def delete(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        binding_id = request.data.get('binding_id')
        if not binding_id:
            return Response({'error': 'binding_id inahitajika'}, status=400)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            success = api.remove_ip_binding(binding_id)
            return Response({'message': 'Binding imefutwa' if success else 'Imeshindwa'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class WalledGardenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            entries = api.get_walled_garden()
            return Response({'entries': entries, 'count': len(entries)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def post(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            dst_host = request.data.get('dst_host', '')
            action   = request.data.get('action', 'allow')
            comment  = request.data.get('comment', '')
            if not dst_host:
                return Response({'error': 'dst_host inahitajika'}, status=400)
            success = api.add_walled_garden(dst_host, action, comment)
            if success:
                return Response({'message': f'{dst_host} imeongezwa kwenye Walled Garden'})
            return Response({'error': 'Imeshindwa kuongeza'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def delete(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        entry_id = request.data.get('entry_id')
        if not entry_id:
            return Response({'error': 'entry_id inahitajika'}, status=400)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            success = api.remove_walled_garden(entry_id)
            return Response({'message': 'Imefutwa' if success else 'Imeshindwa'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class WalledGardenIPView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            entries = api.get_walled_garden_ip()
            return Response({'entries': entries, 'count': len(entries)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def post(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            dst_address = request.data.get('dst_address', '')
            action      = request.data.get('action', 'accept')
            comment     = request.data.get('comment', '')
            if not dst_address:
                return Response({'error': 'dst_address inahitajika'}, status=400)
            success = api.add_walled_garden_ip(dst_address, action, comment)
            if success:
                return Response({'message': f'{dst_address} imeongezwa'})
            return Response({'error': 'Imeshindwa kuongeza'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def delete(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        entry_id = request.data.get('entry_id')
        if not entry_id:
            return Response({'error': 'entry_id inahitajika'}, status=400)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            success = api.remove_walled_garden_ip(entry_id)
            return Response({'message': 'Imefutwa' if success else 'Imeshindwa'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class HotspotCookiesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            cookies = api.get_hotspot_cookies()
            return Response({'cookies': cookies, 'count': len(cookies)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def delete(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            cookie_id = request.data.get('cookie_id')
            if cookie_id:
                success = api.remove_hotspot_cookie(cookie_id)
                return Response({'message': 'Cookie imefutwa' if success else 'Imeshindwa'})
            else:
                success = api.clear_all_cookies()
                return Response({'message': 'Cookies zote zimefutwa' if success else 'Imeshindwa'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class SchedulerView(APIView):
    """System → Scheduler."""
    permission_classes = [IsAuthenticated]

    def get(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            schedulers = api.get_schedulers()
            return Response({'schedulers': schedulers, 'count': len(schedulers)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def post(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            name     = request.data.get('name', '')
            on_event = request.data.get('on_event', '')
            if not name:
                return Response({'error': 'name inahitajika'}, status=400)
            if not on_event:
                return Response({'error': 'on_event (script) inahitajika'}, status=400)
            params = {
                'name':       name,
                'start-date': request.data.get('start_date', 'jan/01/1970'),
                'start-time': request.data.get('start_time', '00:00:00'),
                'interval':   request.data.get('interval', '00:00:00'),
                'on-event':   on_event,
                'policy':     request.data.get('policy', 'read,write,reboot'),
                'comment':    request.data.get('comment', ''),
                'disabled':   request.data.get('disabled', 'false'),
            }
            success = api.add_scheduler(params)
            if success:
                return Response({'message': f'Scheduler "{name}" imeongezwa'})
            return Response({'error': 'Imeshindwa kuongeza scheduler'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def patch(self, request, router_id):
        """
        Hariri scheduler iliyopo (pia enable/disable).
        Frontend inatuma fields mbili njia:
          - Kutoka detail modal (edit): scheduler fields zina hyphen e.g. 'on-event', 'start-date'
          - Kutoka toggle button: { scheduler_id, disabled }
        Tunashughulikia njia zote mbili.
        """
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)

        scheduler_id = request.data.get('scheduler_id')
        if not scheduler_id:
            return Response({'error': 'scheduler_id inahitajika'}, status=400)

        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)

        try:
            params = {'id': scheduler_id}

            # Map: frontend key → MikroTik key
            # Tunakubali njia ZOTE: underscore (kutoka Add form) na hyphen (kutoka detail modal)
            field_map = {
                # underscore style (Add/Edit form)
                'name':       'name',
                'start_date': 'start-date',
                'start_time': 'start-time',
                'interval':   'interval',
                'on_event':   'on-event',
                'policy':     'policy',
                'comment':    'comment',
                'disabled':   'disabled',
                # hyphen style (detail modal direct fields)
                'start-date': 'start-date',
                'start-time': 'start-time',
                'on-event':   'on-event',
            }
            for key, mt_key in field_map.items():
                if key in request.data:
                    params[mt_key] = request.data[key]

            success = api.edit_scheduler(params)
            if success:
                return Response({'message': 'Scheduler imesasishwa'})
            return Response({'error': 'Imeshindwa kusasisha scheduler'}, status=400)
        except Exception as e:
            logger.error(f"Patch scheduler error: {e}")
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

    def delete(self, request, router_id):
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        scheduler_id = request.data.get('scheduler_id')
        if not scheduler_id:
            return Response({'error': 'scheduler_id inahitajika'}, status=400)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            success = api.remove_scheduler(scheduler_id)
            return Response({'message': 'Scheduler imefutwa' if success else 'Imeshindwa'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()
<<<<<<< HEAD



class MikroTikTerminalView(APIView):
    """
    MikroTik Terminal - run commands na kupata matokeo.
    POST → run command moja
    GET  → quick commands zilizopangwa tayari
    """
    permission_classes = [IsAuthenticated]

    # Commands salama zinazoruhusiwa kwa clients
    CLIENT_ALLOWED = [
    # ── SYSTEM ──────────────────────────────────
    '/system/clock/print',
    '/system/clock/set',
    '/system/identity/print',
    '/system/identity/set',
    '/system/resource/print',
    '/system/routerboard/print',
    '/system/health/print',
    '/system/note/print',
    '/system/note/set',
    '/system/reboot',
    '/system/shutdown',

    # ── NTP ─────────────────────────────────────
    '/system/ntp/client/print',
    '/system/ntp/client/set',

    # ── SCHEDULER ───────────────────────────────
    '/system/scheduler/print',
    '/system/scheduler/add',
    '/system/scheduler/set',
    '/system/scheduler/remove',

    # ── LOGGING ─────────────────────────────────
    '/system/logging/print',
    '/log/print',

    # ── IP ──────────────────────────────────────
    '/ip/address/print',
    '/ip/address/add',
    '/ip/address/set',
    '/ip/address/remove',
    '/ip/route/print',
    '/ip/route/add',
    '/ip/route/remove',
    '/ip/dns/print',
    '/ip/dns/set',
    '/ip/arp/print',
    '/ip/pool/print',
    '/ip/pool/add',
    '/ip/pool/set',
    '/ip/pool/remove',
    '/ip/neighbor/print',

    # ── FIREWALL ────────────────────────────────
    '/ip/firewall/filter/print',
    '/ip/firewall/nat/print',
    '/ip/firewall/mangle/print',
    '/ip/firewall/address-list/print',
    '/ip/firewall/address-list/add',
    '/ip/firewall/address-list/remove',

    # ── HOTSPOT ─────────────────────────────────
    '/ip/hotspot/print',
    '/ip/hotspot/set',
    '/ip/hotspot/user/print',
    '/ip/hotspot/user/add',
    '/ip/hotspot/user/set',
    '/ip/hotspot/user/remove',
    '/ip/hotspot/active/print',
    '/ip/hotspot/active/remove',
    '/ip/hotspot/host/print',
    '/ip/hotspot/host/remove',
    '/ip/hotspot/ip-binding/print',
    '/ip/hotspot/ip-binding/add',
    '/ip/hotspot/ip-binding/set',
    '/ip/hotspot/ip-binding/remove',
    '/ip/hotspot/walled-garden/print',
    '/ip/hotspot/walled-garden/add',
    '/ip/hotspot/walled-garden/remove',
    '/ip/hotspot/walled-garden-ip/print',
    '/ip/hotspot/walled-garden-ip/add',
    '/ip/hotspot/walled-garden-ip/remove',
    '/ip/hotspot/cookie/print',
    '/ip/hotspot/cookie/remove',
    '/ip/hotspot/profile/print',
    '/ip/hotspot/profile/set',
    '/ip/hotspot/user/profile/print',
    '/ip/hotspot/user/profile/set',

    # ── INTERFACE ───────────────────────────────
    '/interface/print',
    '/interface/set',
    '/interface/enable',
    '/interface/disable',
    '/interface/ethernet/print',
    '/interface/wireless/print',
    '/interface/wireless/set',
    '/interface/wireless/registration-table/print',
    '/interface/bridge/print',
    '/interface/bridge/port/print',

    # ── DHCP ────────────────────────────────────
    '/ip/dhcp-server/print',
    '/ip/dhcp-server/set',
    '/ip/dhcp-server/lease/print',
    '/ip/dhcp-server/lease/add',
    '/ip/dhcp-server/lease/remove',
    '/ip/dhcp-server/network/print',
    '/ip/dhcp-client/print',

    # ── QUEUE ───────────────────────────────────
    '/queue/simple/print',
    '/queue/simple/add',
    '/queue/simple/set',
    '/queue/simple/remove',
    '/queue/tree/print',
    '/queue/type/print',

    # ── PINGS & TOOLS ───────────────────────────
    '/ping',
    '/tool/ping',
    '/tool/traceroute',
    '/tool/bandwidth-test',
    '/tool/fetch',

    # ── PPP ─────────────────────────────────────
    '/ppp/secret/print',
    '/ppp/active/print',

    # ── CERTIFICATE ─────────────────────────────
    '/certificate/print',

    # ── RADIUS ──────────────────────────────────
    '/radius/print',
    '/radius/add',
    '/radius/set',
    '/radius/remove',
]

    def get(self, request, router_id):
        """Rudisha quick commands zilizopangwa."""
        quick_commands = [
            {
                'category': 'System',
                'commands': [
                    {'label': '🕐 Angalia Saa na Timezone', 'cmd': '/system/clock/print', 'fix': None},
                    {'label': '🌍 Weka Timezone Africa/Nairobi', 'cmd': '/system/clock/set', 'params': {'time-zone-name': 'Africa/Nairobi'}, 'fix': 'timezone'},
                    {'label': '📋 System Info', 'cmd': '/system/resource/print', 'fix': None},
                    {'label': '🔖 Router Identity', 'cmd': '/system/identity/print', 'fix': None},
                ]
            },
            {
                'category': 'Hotspot',
                'commands': [
                    {'label': '👥 Hotspot Users Count', 'cmd': '/ip/hotspot/user/print', 'fix': None},
                    {'label': '✅ Active Sessions', 'cmd': '/ip/hotspot/active/print', 'fix': None},
                    {'label': '📅 Schedulers Zote', 'cmd': '/system/scheduler/print', 'fix': None},
                ]
            },
            {
                'category': 'Network',
                'commands': [
                    {'label': '🌐 IP Addresses', 'cmd': '/ip/address/print', 'fix': None},
                    {'label': '📡 Interfaces', 'cmd': '/interface/print', 'fix': None},
                    {'label': '🔒 DNS Settings', 'cmd': '/ip/dns/print', 'fix': None},
                ]
            },
        ]
        return Response({'quick_commands': quick_commands})

    def post(self, request, router_id):
        """Run command na rudisha matokeo."""
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)

        raw_command = request.data.get('command', '').strip()
        params  = dict(request.data.get('params', {}) or {})
        queries = request.data.get('queries', {})

        # Gawa command path na inline params (mfano: "/system/clock/set date=jul/25/2026 time=17:34:00")
        # Terminal ya frontend inatuma kila kitu kama field moja ya 'command' —
        # bila kugawa hivi, MikroTik inapokea path+params kama string moja
        # isiyoeleweka ("no such command prefix").
        parts = raw_command.split()
        command = parts[0] if parts else raw_command
        for token in parts[1:]:
            if '=' in token:
                key, _, value = token.partition('=')
                params[key] = value

        if not command:
            return Response({'error': 'command inahitajika'}, status=400)

        # Clients wanaweza run commands salama tu
        # Super admins wanaweza run command yoyote
        if not request.user.is_superadmin():
            allowed = any(command.startswith(c) for c in self.CLIENT_ALLOWED)
            if not allowed:
                return Response({'error': 'Huna ruhusa ya command hii'}, status=403)

        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)

        try:
            result = api.command(command, params or None, queries or None)
            return Response({
                'success': True,
                'command': command,
                'result': result,
                'count': len(result) if isinstance(result, list) else 0,
            })
        except Exception as e:
            logger.error(f"Terminal command error: {e}")
            return Response({
                'success': False,
                'command': command,
                'error': str(e),
            }, status=400)
        finally:
            api.disconnect()

=======
>>>>>>> ce77eb29d3fbe067206773bcdacb85bba7fb4c3c
