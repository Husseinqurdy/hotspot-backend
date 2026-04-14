import socket
import hashlib
import logging

logger = logging.getLogger('netsafi')


class MikroTikAPI:
    """Inawasiliana na MikroTik RouterOS kupitia API port 8728 (VPN)."""

    def __init__(self, host, port=8728, username='admin', password=''):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sock = None
        self.connected = False

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.host, self.port))
            self._login()
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"MikroTik connect failed {self.host}: {e}")
            return False

    def disconnect(self):
        if self.sock:
            try: self.sock.close()
            except: pass
        self.connected = False

    def _write_len(self, l):
        if l < 0x80: self.sock.sendall(bytes([l]))
        elif l < 0x4000:
            l |= 0x8000; self.sock.sendall(bytes([(l>>8)&0xFF, l&0xFF]))
        else:
            l |= 0xC0000000
            self.sock.sendall(bytes([(l>>24)&0xFF,(l>>16)&0xFF,(l>>8)&0xFF,l&0xFF]))

    def _read_len(self):
        b = ord(self.sock.recv(1))
        if b < 0x80: return b
        elif b < 0xC0: return ((b&0x3F)<<8)|ord(self.sock.recv(1))
        else:
            b2,b3,b4 = ord(self.sock.recv(1)),ord(self.sock.recv(1)),ord(self.sock.recv(1))
            return ((b&0x0F)<<24)|(b2<<16)|(b3<<8)|b4

    def _write_sentence(self, s):
        for w in s:
            e = w.encode('utf-8'); self._write_len(len(e)); self.sock.sendall(e)
        self._write_len(0)

    def _read_sentence(self):
        s = []
        while True:
            l = self._read_len()
            if l == 0: return s
            w = b''
            while len(w) < l: w += self.sock.recv(l-len(w))
            s.append(w.decode('utf-8'))

    def _talk(self, sentence):
        self._write_sentence(sentence)
        reply = []
        while True:
            s = self._read_sentence()
            if s: reply.append(s[0])
            if s and s[0] in ('!done', '!trap'): break
        return reply

    def _login(self):
        reply = self._talk(['/login', f'=name={self.username}', f'=password={self.password}'])
        if reply and reply[0] == '!done': return
        for item in reply:
            if '=ret=' in item:
                ch = item.split('=ret=')[1]
                md5 = hashlib.md5()
                md5.update(b'\x00'); md5.update(self.password.encode()); md5.update(bytes.fromhex(ch))
                self._talk(['/login', f'=name={self.username}', f'=response=00{md5.hexdigest()}'])

    def command(self, cmd, params=None):
        sentence = [cmd]
        if params:
            for k, v in params.items(): sentence.append(f'={k}={v}')
        self._write_sentence(sentence)
        results = []
        while True:
            s = self._read_sentence()
            if not s: break
            if s[0] == '!done': break
            if s[0] == '!trap': raise Exception(f"MikroTik: {' '.join(s[1:])}")
            if s[0] == '!re':
                row = {}
                for item in s[1:]:
                    if '=' in item: k, v = item[1:].split('=', 1); row[k] = v
                results.append(row)
        return results

    def is_alive(self):
        try: return len(self.command('/system/identity/print')) > 0
        except: return False

    def add_hotspot_user(self, username, password, profile, comment=''):
        try:
            self.command('/ip/hotspot/user/add', {
                'name': username, 'password': password,
                'profile': profile, 'comment': comment
            })
            return True
        except Exception as e:
            logger.error(f"Failed add user {username}: {e}")
            return False

    def remove_hotspot_user(self, username):
        try:
            users = self.command('/ip/hotspot/user/print', {'?name': username})
            for u in users: self.command('/ip/hotspot/user/remove', {'=.id': u['.id']})
            return True
        except: return False

    def get_active_sessions(self):
        try: return self.command('/ip/hotspot/active/print')
        except: return []

    def add_hotspot_profile(self, name, rate_limit, session_timeout, shared_users=1):
        try:
            self.command('/ip/hotspot/user/profile/add', {
                'name': name, 'rate-limit': rate_limit,
                'session-timeout': session_timeout, 'shared-users': str(shared_users)
            })
            return True
        except Exception as e:
            logger.error(f"Failed add profile {name}: {e}")
            return False


def get_mikrotik_connection(router):
    """Pata MikroTik connection kupitia VPN IP."""
    api = MikroTikAPI(
        host=router.host,
        port=router.api_port,
        username=router.api_username,
        password=router.api_password,
    )
    return api if api.connect() else None
