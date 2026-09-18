from django.db import migrations


def backfill_payment_device(apps, schema_editor):
    """
    Kwa Payments za zamani zenye 'device_id' (string) inayolingana na
    GSMDevice.device_id iliyopo, weka FK 'gsm_device' moja kwa moja.
    Hii ni salama kufanya kiotomatiki kwa sababu ni MATCH YA MOJA KWA
    MOJA (si uamuzi wa kibiashara) — device_id ilikuwa tayari
    ikirekodiwa kwenye kila Payment tangu mwanzo.

    Payments zisizo na device_id (au ambazo device_id yake haipo tena
    kwenye GSMDevice) zitabaki na gsm_device=None — hazitaathiri
    chochote, ni kwa ajili ya historia/audit tu.
    """
    Payment = apps.get_model('payments', 'Payment')
    GSMDevice = apps.get_model('devices', 'GSMDevice')

    device_pk_by_device_id = {d.device_id: d.pk for d in GSMDevice.objects.all()}

    candidates = Payment.objects.filter(gsm_device__isnull=True).exclude(
        device_id__isnull=True
    ).exclude(device_id='')

    updated = 0
    for payment in candidates:
        device_pk = device_pk_by_device_id.get(payment.device_id)
        if device_pk:
            Payment.objects.filter(pk=payment.pk).update(gsm_device_id=device_pk)
            updated += 1


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0004_clientpackageprice_per_client_payment_device'),
    ]

    operations = [
        migrations.RunPython(backfill_payment_device, reverse_noop),
    ]
