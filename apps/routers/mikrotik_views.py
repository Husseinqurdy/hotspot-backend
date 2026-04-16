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
    """Hali kamili ya router - kama System → Resources kwenye Winbox."""
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
    """Interfaces zote za router."""
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
    """IP addresses za router."""
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
    """Hotspot users - ona, ongeza, futa."""
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
        """Ongeza hotspot user manually."""
        router = get_router_for_user(router_id, request.user)
        if not router:
            return Response({'error': 'Router haikupatikana'}, status=404)
        api = get_mikrotik_connection(router)
        if not api:
            return Response({'error': 'Router haipo online'}, status=503)
        try:
            username = request.data.get('username', '')
            password = request.data.get('password', username)
            profile = request.data.get('profile', 'default')
            comment = request.data.get('comment', 'Manual')
            success = api.add_hotspot_user(username, password, profile, comment)
            if success:
                return Response({'message': f'User {username} ameongezwa'})
            return Response({'error': 'Imeshindwa kuongeza user'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            api.disconnect()


class HotspotUserDeleteView(APIView):
    """Futa hotspot user."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, router_id, username):
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
    """Active sessions - watumiaji waliounganishwa sasa."""
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
        """Disconnect session."""
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
    """Hotspot profiles."""
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


class RouterRestartView(APIView):
    """Restart router remotely."""
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
    """Bandwidth monitoring."""
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
            for iface in interfaces[:5]:  # Top 5 interfaces
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
    """Firewall rules."""
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
    """System logs."""
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
    """DNS settings."""
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
