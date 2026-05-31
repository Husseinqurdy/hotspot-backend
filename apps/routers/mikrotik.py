import socket
import hashlib
import logging

logger = logging.getLogger('netsafi')


class MikroTikAPI:
    """MikroTik RouterOS API - inawasiliana kupitia WireGuard VPN."""

    def __init__(self, host, port=8728, username='admin', password='', timeout=10):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.sock = None
        self.connected = False

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            self._login()
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"MikroTik connect failed {self.host}: {e}")
            return False

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    def _write_len(self, l):
        if l < 0x80:
            self.sock.sendall(bytes([l]))
        elif l < 0x4000:
            l |= 0x8000
            self.sock.sendall(bytes([(l >> 8) & 0xFF, l & 0xFF]))
        else:
            l |= 0xC0000000
            self.sock.sendall(bytes([(l >> 24) & 0xFF, (l >> 16) & 0xFF, (l >> 8) & 0xFF, l & 0xFF]))

    def _read_len(self):
        b = ord(self.sock.recv(1))
        if b < 0x80:
            return b
        elif b < 0xC0:
            return ((b & 0x3F) << 8) | ord(self.sock.recv(1))
        else:
            b2, b3, b4 = ord(self.sock.recv(1)), ord(self.sock.recv(1)), ord(self.sock.recv(1))
            return ((b & 0x0F) << 24) | (b2 << 16) | (b3 << 8) | b4

    def _write_sentence(self, s):
        for w in s:
            e = w.encode('utf-8')
            self._write_len(len(e))
            self.sock.sendall(e)
        self._write_len(0)

    def _read_sentence(self):
        s = []
        while True:
            l = self._read_len()
            if l == 0:
                return s
            w = b''
            while len(w) < l:
                w += self.sock.recv(l - len(w))
            s.append(w.decode('utf-8', errors='replace'))

    def _talk(self, sentence):
        self._write_sentence(sentence)
        reply = []
        while True:
            s = self._read_sentence()
            if s:
                reply.append(s[0])
            if s and s[0] in ('!done', '!trap'):
                break
        return reply

    def _login(self):
        reply = self._talk(['/login', f'=name={self.username}', f'=password={self.password}'])
        if reply and reply[0] == '!done':
            return
        for item in reply:
            if '=ret=' in item:
                ch = item.split('=ret=')[1]
                md5 = hashlib.md5()
                md5.update(b'\x00')
                md5.update(self.password.encode())
                md5.update(bytes.fromhex(ch))
                self._talk(['/login', f'=name={self.username}', f'=response=00{md5.hexdigest()}'])

    def command(self, cmd, params=None, queries=None):
        sentence = [cmd]
        if params:
            for k, v in params.items():
                sentence.append(f'={k}={v}')
        if queries:
            for k, v in queries.items():
                sentence.append(f'?{k}={v}')
        self._write_sentence(sentence)
        results = []
        while True:
            s = self._read_sentence()
            if not s:
                break
            if s[0] == '!done':
                break
            if s[0] == '!trap':
                raise Exception(f"MikroTik error: {' '.join(s[1:])}")
            if s[0] == '!re':
                row = {}
                for item in s[1:]:
                    if '=' in item:
                        k, v = item[1:].split('=', 1)
                        row[k] = v
                results.append(row)
        return results

    # ── SYSTEM ────────────────────────────────────────────

    def get_identity(self):
        r = self.command('/system/identity/print')
        return r[0].get('name', 'Unknown') if r else 'Unknown'

    def get_resource(self):
        r = self.command('/system/resource/print')
        return r[0] if r else {}

    def get_routerboard(self):
        r = self.command('/system/routerboard/print')
        return r[0] if r else {}

    def restart(self):
        try:
            self.command('/system/reboot')
            return True
        except:
            return True  # Connection drops after reboot

    def is_alive(self):
        try:
            return bool(self.command('/system/identity/print'))
        except:
            return False

    # ── INTERFACES ────────────────────────────────────────

    def get_interfaces(self):
        return self.command('/interface/print')

    def get_interface_stats(self):
        return self.command('/interface/print', {'stats': ''})

    # ── IP ADDRESSES ──────────────────────────────────────

    def get_ip_addresses(self):
        return self.command('/ip/address/print')

    def get_routes(self):
        return self.command('/ip/route/print')

    def get_dns(self):
        r = self.command('/ip/dns/print')
        return r[0] if r else {}

    # ── HOTSPOT ───────────────────────────────────────────

    def get_hotspot_users(self):
        return self.command('/ip/hotspot/user/print')

    def add_hotspot_user(self, username, password, profile, comment=''):
        try:
            self.command('/ip/hotspot/user/add', {
                'name': username,
                'password': password,
                'profile': profile,
                'comment': comment
            })
            return True
        except Exception as e:
            logger.error(f"Add hotspot user failed: {e}")
            return False

    def delete_hotspot_user(self, username):
        try:
            users = self.command('/ip/hotspot/user/print', queries={'name': username})
            for u in users:
                self.command('/ip/hotspot/user/remove', {'.id': u['.id']})
            return True
        except Exception as e:
            logger.error(f"Delete hotspot user failed: {e}")
            return False

    def get_active_sessions(self):
        return self.command('/ip/hotspot/active/print')

    def disconnect_session(self, session_id):
        try:
            self.command('/ip/hotspot/active/remove', {'.id': session_id})
            return True
        except:
            return False

    def get_hotspot_profiles(self):
        return self.command('/ip/hotspot/user/profile/print')

    def add_hotspot_profile(self, name, rate_limit, session_timeout, shared_users=1):
        try:
            self.command('/ip/hotspot/user/profile/add', {
                'name': name,
                'rate-limit': rate_limit,
                'session-timeout': session_timeout,
                'shared-users': str(shared_users)
            })
            return True
        except Exception as e:
            logger.error(f"Add profile failed: {e}")
            return False

    def remove_hotspot_user(self, username):
        return self.delete_hotspot_user(username)

    # ── FIREWALL ──────────────────────────────────────────

    def get_firewall_rules(self):
        return self.command('/ip/firewall/filter/print')

    def get_nat_rules(self):
        return self.command('/ip/firewall/nat/print')

    # ── BANDWIDTH / TRAFFIC ───────────────────────────────

    def get_interface_traffic(self, interface_name):
        try:
            return self.command('/interface/monitor-traffic', {
                'interface': interface_name,
                'once': ''
            })
        except:
            return []

    # ── LOGS ──────────────────────────────────────────────

    def get_logs(self, limit=50):
        logs = self.command('/log/print')
        return logs[-limit:] if len(logs) > limit else logs

    # ── WIRELESS ──────────────────────────────────────────

    def get_wireless_clients(self):
        try:
            return self.command('/interface/wireless/registration-table/print')
        except:
            return []

    # ── HOTSPOT SERVERS ───────────────────────────────────

    def get_hotspot_servers(self):
        """IP/Hotspot → Servers"""
        return self.command('/ip/hotspot/print')

    # ── HOTSPOT HOSTS ─────────────────────────────────────

    def get_hotspot_hosts(self):
        """IP/Hotspot → Hosts - vifaa vyote vilivyounganika"""
        return self.command('/ip/hotspot/host/print')

    # ── IP BINDINGS ───────────────────────────────────────

    def get_ip_bindings(self):
        """IP/Hotspot → IP Bindings"""
        return self.command('/ip/hotspot/ip-binding/print')

    def add_ip_binding(self, mac_address, ip_address='', binding_type='regular', comment=''):
        """Ongeza IP Binding"""
        try:
            params = {
                'mac-address': mac_address,
                'type': binding_type,
            }
            if ip_address:
                params['address'] = ip_address
            if comment:
                params['comment'] = comment
            self.command('/ip/hotspot/ip-binding/add', params)
            return True
        except Exception as e:
            logger.error(f"Add IP binding failed: {e}")
            return False

    def remove_ip_binding(self, binding_id):
        """Futa IP Binding"""
        try:
            self.command('/ip/hotspot/ip-binding/remove', {'.id': binding_id})
            return True
        except Exception as e:
            logger.error(f"Remove IP binding failed: {e}")
            return False

    # ── WALLED GARDEN ─────────────────────────────────────

    def get_walled_garden(self):
        """IP/Hotspot → Walled Garden (HTTP)"""
        return self.command('/ip/hotspot/walled-garden/print')

    def add_walled_garden(self, dst_host, action='allow', comment=''):
        """Ongeza Walled Garden entry"""
        try:
            params = {'dst-host': dst_host, 'action': action}
            if comment:
                params['comment'] = comment
            self.command('/ip/hotspot/walled-garden/add', params)
            return True
        except Exception as e:
            logger.error(f"Add walled garden failed: {e}")
            return False

    def remove_walled_garden(self, entry_id):
        """Futa Walled Garden entry"""
        try:
            self.command('/ip/hotspot/walled-garden/remove', {'.id': entry_id})
            return True
        except Exception as e:
            logger.error(f"Remove walled garden failed: {e}")
            return False

    # ── WALLED GARDEN IP ──────────────────────────────────

    def get_walled_garden_ip(self):
        """IP/Hotspot → Walled Garden IP List (HTTPS/IP)"""
        return self.command('/ip/hotspot/walled-garden/ip/print')

    def add_walled_garden_ip(self, dst_address, action='accept', comment=''):
        """Ongeza Walled Garden IP entry"""
        try:
            params = {'dst-address': dst_address, 'action': action}
            if comment:
                params['comment'] = comment
            self.command('/ip/hotspot/walled-garden/ip/add', params)
            return True
        except Exception as e:
            logger.error(f"Add walled garden IP failed: {e}")
            return False

    def remove_walled_garden_ip(self, entry_id):
        """Futa Walled Garden IP entry"""
        try:
            self.command('/ip/hotspot/walled-garden/ip/remove', {'.id': entry_id})
            return True
        except Exception as e:
            logger.error(f"Remove walled garden IP failed: {e}")
            return False

    # ── COOKIES ───────────────────────────────────────────

    def get_hotspot_cookies(self):
        """IP/Hotspot → Cookies"""
        return self.command('/ip/hotspot/cookie/print')

    def remove_hotspot_cookie(self, cookie_id):
        """Futa cookie moja"""
        try:
            self.command('/ip/hotspot/cookie/remove', {'.id': cookie_id})
            return True
        except Exception as e:
            logger.error(f"Remove cookie failed: {e}")
            return False

    def clear_all_cookies(self):
        """Futa cookies zote"""
        try:
            cookies = self.get_hotspot_cookies()
            for c in cookies:
                self.command('/ip/hotspot/cookie/remove', {'.id': c['.id']})
            return True
        except Exception as e:
            logger.error(f"Clear all cookies failed: {e}")
            return False

    # ── SCHEDULER ─────────────────────────────────────────

    def get_schedulers(self):
        """System → Scheduler - orodha ya schedulers zote."""
        return self.command('/system/scheduler/print')

    def add_scheduler(self, params):
        """Ongeza scheduler mpya.

        params ni dict inayoweza kuwa na:
          name, start-date, start-time, interval,
          on-event, policy, comment, disabled
        """
        try:
            self.command('/system/scheduler/add', params)
            return True
        except Exception as e:
            logger.error(f"Add scheduler failed: {e}")
            return False

    def edit_scheduler(self, params):
        """Hariri scheduler iliyopo.

        params lazima iwe na '.id' ya scheduler inayolengwa.
        Fields zingine ni za hiari — tuma tu zinazobadilika.
        """
        try:
            self.command('/system/scheduler/set', params)
            return True
        except Exception as e:
            logger.error(f"Edit scheduler failed: {e}")
            return False

    def remove_scheduler(self, scheduler_id):
        """Futa scheduler kwa .id yake."""
        try:
            self.command('/system/scheduler/remove', {'.id': scheduler_id})
            return True
        except Exception as e:
            logger.error(f"Remove scheduler failed: {e}")
            return False


def get_mikrotik_connection(router):
    """Pata MikroTik connection kupitia WireGuard VPN."""
    api = MikroTikAPI(
        host=router.host,
        port=router.api_port,
        username=router.api_username,
        password=router.api_password,
    )
    return api if api.connect() else None
