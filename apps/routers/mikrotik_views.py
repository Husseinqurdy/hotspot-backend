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
        """Ongeza hotspot user mpya."""
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
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
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()

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
