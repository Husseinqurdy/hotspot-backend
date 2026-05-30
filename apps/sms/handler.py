import re
import time
import hashlib
import logging
import serial
from django.conf import settings

logger = logging.getLogger('hotspot')


class SIM800CHandler:
    """
    Inasimamia SIM 800C GSM Module kupitia Serial port.
    Inasoma SMS za malipo na kutuma SMS za vouchers.
    """

    def __init__(self):
        self.port = settings.SIM800C_PORT
        self.baudrate = settings.SIM800C_BAUDRATE
        self.serial_conn = None

    def connect(self):
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=2,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
            )
            time.sleep(1)
            self._send_at('AT')
            self._send_at('AT+CMGF=1')   # Text mode
            self._send_at('AT+CNMI=1,2,0,0,0')  # Arifu SMS mpya
            logger.info("SIM 800C imeunganishwa")
            return True
        except Exception as e:
            logger.error(f"SIM 800C imeshindwa: {e}")
            return False

    def disconnect(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

    def _send_at(self, command, wait=0.3):
        """Tuma AT command na rudisha response."""
        if not self.serial_conn or not self.serial_conn.is_open:
            return ''
        self.serial_conn.write((command + '\r\n').encode())
        time.sleep(wait)
        response = ''
        while self.serial_conn.in_waiting:
            response += self.serial_conn.read(
                self.serial_conn.in_waiting
            ).decode('utf-8', errors='ignore')
        return response

    def is_alive(self):
        """Angalia kama SIM 800C ipo online."""
        response = self._send_at('AT')
        return 'OK' in response

    def read_unread_sms(self):
        """Soma na rudisha SMS zote ambazo hazijakusomwa."""
        response = self._send_at('AT+CMGL="REC UNREAD"', wait=1.5)
        messages = self._parse_sms_list(response)
        return messages

    def _parse_sms_list(self, raw):
        """Chambua response ya AT+CMGL na rudisha list ya messages."""
        messages = []
        lines = raw.strip().split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('+CMGL:'):
                try:
                    parts = line.split(',')
                    index = parts[0].split(':')[1].strip()
                    phone = parts[2].strip().strip('"')
                    sms_text = lines[i + 1].strip() if i + 1 < len(lines) else ''
                    if sms_text and sms_text != 'OK':
                        messages.append({
                            'index': index,
                            'phone': phone,
                            'text': sms_text,
                        })
                    # Futa SMS baada ya kusoma
                    self._send_at(f'AT+CMGD={index}')
                except (IndexError, ValueError):
                    pass
            i += 1
        return messages

    def send_sms(self, phone, message):
        """Tuma SMS kwa namba fulani."""
        try:
            phone = self._normalize_phone(phone)
            self._send_at(f'AT+CMGS="{phone}"', wait=0.5)
            self.serial_conn.write((message + '\x1A').encode())
            time.sleep(3)
            response = ''
            if self.serial_conn.in_waiting:
                response = self.serial_conn.read(
                    self.serial_conn.in_waiting
                ).decode('utf-8', errors='ignore')
            success = 'OK' in response or '+CMGS' in response
            if success:
                logger.info(f"SMS imetumwa kwa {phone}")
            else:
                logger.error(f"SMS imeshindwa kwa {phone}: {response}")
            return success
        except Exception as e:
            logger.error(f"Hitilafu ya SMS: {e}")
            return False

    def _normalize_phone(self, phone):
        """Badilisha namba ya simu kuwa format ya kimataifa."""
        phone = phone.strip()
        if phone.startswith('0'):
            return '+255' + phone[1:]
        elif phone.startswith('255'):
            return '+' + phone
        return phone


class SMSParser:
    """
    Inachambua SMS za malipo kutoka mitandao yote ya Tanzania.
    Inaunga mkono: M-Pesa, Tigo Pesa, Airtel Money, HaloPesa.
    """

    # Patterns za kila mtandao
    PATTERNS = [
        {
            'network': 'mpesa',
            'pattern': r'TZS\s*([\d,]+\.?\d*)\s+paid\s+to\s+\w+\s+Ref\s+(\w+)',
        },
        {
            'network': 'mpesa',
            'pattern': r'Confirmed\.\s*TZS\s*([\d,]+)\s+sent.*?Ref[:\s]+(\w+)',
        },
        {
            'network': 'tigo',
            'pattern': r'Umelipa\s+TZS\s+([\d,]+)\s+kwa\s+\w+[.\s]+Kumbukumbu\s+namba\s+(\w+)',
        },
        {
            'network': 'airtel',
            'pattern': r'Confirmed\.\s+TZS([\d,]+)\s+sent\s+to[\w\s]+Ref[:\s]+(\w+)',
        },
        {
            'network': 'halopesa',
            'pattern': r'Malipo\s+ya\s+TZS\s+([\d,]+)\s+yamefanikiwa.*?kumbukumbu[:\s]+(\w+)',
        },
        {
            # Generic fallback
            'network': 'generic',
            'pattern': r'(?:TZS|Tsh)[.\s]*([\d,]+).*?(?:Ref|ref|REF|kumbukumbu)[:\s]+(\w{4})',
        },
    ]

    @classmethod
    def parse(cls, sms_text):
        """
        Chambua SMS na rudisha dict yenye amount, reference, network.
        Rudisha None kama si SMS ya malipo.
        """
        for pattern_info in cls.PATTERNS:
            match = re.search(pattern_info['pattern'], sms_text, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount = float(amount_str)
                    reference = match.group(2).upper().strip()
                    if amount > 0 and len(reference) >= 4:
                        return {
                            'amount': amount,
                            'reference': reference,
                            'network': pattern_info['network'],
                        }
                except (ValueError, IndexError):
                    continue
        return None

    @classmethod
    def get_sms_hash(cls, text):
        """Pata hash ya SMS kuzuia duplicate processing."""
        return hashlib.sha256(text.encode()).hexdigest()