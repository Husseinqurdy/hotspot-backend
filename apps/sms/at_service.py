"""
Njia ya PILI, huru kabisa, ya kutuma SMS — kupitia Africa's Talking API
(one-way, moja kwa moja). Hii HAIHUSIANI na mfumo uliopo wa GSM
(OutgoingSMS queue kwenye apps/sms/models.py + devices za GSM). Zote mbili
zinaishi pamoja bila kugongana:

  - GSM (OutgoingSMS)  → kwa SMS zinazohitaji kutumwa kupitia simu za GSM
                          zilizounganishwa (poll-based queue).
  - Africa's Talking   → kwa SMS za mfumo (ripoti, arifa za admin, n.k)
                          zinazotumwa moja kwa moja, papo hapo, kupitia API.

Matumizi:
    from apps.sms.at_service import send_at_sms
    send_at_sms('0712345678', 'Ujumbe wako hapa')
"""
import logging
from django.conf import settings

logger = logging.getLogger('netsafi')

_at_sms_client = None


def _get_at_sms_client():
    """
    Lazy singleton — SDK inaanzishwa mara moja tu, inapohitajika kwa mara
    ya kwanza, si kwenye import ya module (inazuia crash wakati wa
    kuanzisha Django kama settings hazijawekwa bado, mfano wakati wa
    migrations/tests).
    """
    global _at_sms_client
    if _at_sms_client is None:
        import africastalking
        africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
        _at_sms_client = africastalking.SMS
    return _at_sms_client


def _normalize_phone(phone: str) -> str:
    """
    Africa's Talking inahitaji namba ya kimataifa (+255XXXXXXXXX).
    Namba zetu DB mara nyingi zimehifadhiwa kama 07XXXXXXXX.
    """
    phone = (phone or '').strip().replace(' ', '').replace('-', '')
    if phone.startswith('+255'):
        return phone
    if phone.startswith('255'):
        return '+' + phone
    if phone.startswith('0'):
        return '+255' + phone[1:]
    return phone


def send_at_sms(phone: str, message: str) -> bool:
    """
    Tuma SMS MOJA kwa moja (one-way) kupitia Africa's Talking.

    MUHIMU: hii ni "best-effort" — HAIWAHI kuinua exception kwenda juu.
    SMS ni nyongeza (side-effect) ya matukio kama ripoti za mauzo au
    maombi ya kutoa fedha; ikiwa itashindwa (mtandao, credit imeisha,
    namba mbovu, n.k), logic kuu (kuunda ripoti, kuunda withdrawal,
    kuunda Notification ya in-app) HAIPASWI kuvunjika.

    Inarudisha True ikiwa ombi limetumwa kwa Africa's Talking bila
    exception (siyo uthibitisho wa 100% kwamba mpokeaji ameipata),
    au False ikiwa imeshindikana / imezimwa.
    """
    if not phone:
        logger.warning('send_at_sms: hakuna namba ya simu, SMS haijatumwa')
        return False

    if not getattr(settings, 'AT_USERNAME', '') or not getattr(settings, 'AT_API_KEY', ''):
        logger.warning('send_at_sms: AT_USERNAME/AT_API_KEY hazijawekwa kwenye settings — SMS haijatumwa')
        return False

    recipient = _normalize_phone(phone)

    try:
        sms = _get_at_sms_client()
        kwargs = {'recipients': [recipient]}
        sender_id = getattr(settings, 'AT_SENDER_ID', '')
        if sender_id:
            kwargs['sender_id'] = sender_id
        response = sms.send(message, **kwargs)
        logger.info(f"send_at_sms → {recipient}: {response}")
        return True
    except Exception as e:
        logger.error(f"send_at_sms imeshindwa kwa {recipient}: {e}")
        return False

