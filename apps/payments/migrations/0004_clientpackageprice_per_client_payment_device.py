import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0004_gsmdevice_provisioning'),
        ('payments', '0003_withdrawalrequest'),
    ]

    operations = [
        # KABLA: unique=True globally. SASA: matching inaanzia kwa
        # GSMDevice.eligible_clients() (device_id → client(s)), kwa
        # hiyo amount inahitaji kuwa ya kipekee TU ndani ya kundi la
        # eligible_clients (angalia apps/packages/models.py::Package.clean()).
        migrations.AlterField(
            model_name='clientpackageprice',
            name='unique_amount',
            field=models.PositiveIntegerField(),
        ),
        migrations.AddConstraint(
            model_name='clientpackageprice',
            constraint=models.UniqueConstraint(fields=('client', 'unique_amount'), name='unique_amount_per_client'),
        ),
        # MPYA: rejea ya moja kwa moja kwa GSMDevice iliyoleta malipo
        # haya. Imeitwa 'gsm_device' (SIYO 'device') ili kuepuka
        # mgongano wa attname na field ya zamani 'device_id'
        # (CharField) — FK inayoitwa 'device' ingeunda 'device_id'
        # kiotomatiki. null=True kwa sababu Payments za zamani zina
        # device_id ya string tu, si FK — zitajazwa na data migration
        # inayofuata endapo device husika ina rekodi ya GSMDevice
        # yenye device_id inayolingana.
        migrations.AddField(
            model_name='payment',
            name='gsm_device',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='payments',
                to='devices.gsmdevice',
            ),
        ),
    ]
